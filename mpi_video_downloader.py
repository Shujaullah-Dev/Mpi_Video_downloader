import json
import os
import time
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from mpi4py import MPI
import yt_dlp

def download_video(url, output_dir, quality='best', max_retries=2):
    """Downloads a single video using yt-dlp with retry logic."""
    
    for attempt in range(max_retries + 1):
        try:
            # Configure quality format
            if quality == 'best':
                format_str = 'bestvideo+bestaudio/best'
            elif quality == 'worst':
                format_str = 'worstvideo+worstaudio/worst'
            elif quality in ['720p', '1080p', '480p']:
                height = quality.replace('p', '')
                format_str = f'bestvideo[height<={height}]+bestaudio/best[height<={height}]'
            else:
                format_str = 'bestvideo+bestaudio/best'
            
            ydl_opts = {
                'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
                'format': format_str,
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': False,
                'no_color': True,
                'js_runtimes': {'node': {}},
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return {
                    'status': 'success',
                    'url': url,
                    'title': info.get('title', 'Unknown'),
                    'file_path': ydl.prepare_filename(info),
                    'time': 0,  # Will be set by caller
                    'attempts': attempt + 1
                }
                
        except Exception as e:
            error_msg = str(e)
            
            if attempt < max_retries:
                # Wait before retry
                time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s...
                continue
            else:
                # Final attempt failed
                return {
                    'status': 'error',
                    'url': url,
                    'title': 'Failed',
                    'error': error_msg,
                    'attempts': attempt + 1,
                    'time': 0
                }
    
    # Should not reach here
    return {
        'status': 'error',
        'url': url,
        'error': 'Unknown error',
        'attempts': max_retries + 1,
        'time': 0
    }

def check_pause_flag(output_dir):
    """Check if pause flag exists."""
    pause_flag = os.path.join(output_dir, "pause.flag")
    return os.path.exists(pause_flag)

def write_status(status_file, status_data):
    """Write status to file with retry and atomic replacement."""
    temp_file = f"{status_file}.tmp.{os.getpid()}"
    for _ in range(5):
        try:
            os.makedirs(os.path.dirname(status_file), exist_ok=True)
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, indent=2)
            os.replace(temp_file, status_file)
            return True
        except Exception:
            time.sleep(0.05)
    return False

def main():
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()

    # Load Config
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config.json')
    
    if not os.path.exists(config_path):
        if rank == 0:
            print("ERROR: Config file not found.", file=sys.stderr)
        return

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        if rank == 0:
            print(f"ERROR: Failed to load config: {e}", file=sys.stderr)
        return

    # Extract config
    urls = config.get('urls', [])
    output_dir = os.path.abspath(os.path.join(script_dir, config.get('output_dir', 'downloads')))
    retry_failed = config.get('retry_failed', True)
    max_retries = config.get('max_retries', 2) if retry_failed else 0
    video_quality = config.get('video_quality', 'best')
    
    # Create output directory
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        print(f"Rank {rank}: Failed to create output directory '{output_dir}': {e}", file=sys.stderr)

    if rank == 0:
        print(f"[Master] Starting download of {len(urls)} URLs with {size} ranks")
        print(f"[Master] Quality: {video_quality}, Max retries: {max_retries}")
    
    # Distribute URLs (Round Robin)
    my_urls = [url for i, url in enumerate(urls) if i % size == rank]
    
    if rank == 0:
        print(f"[Master] URL distribution: {[len([u for i, u in enumerate(urls) if i % size == r]) for r in range(size)]}")
    
    # Status file for this rank
    status_file = os.path.join(output_dir, f'status_rank_{rank}.json')
    
    results = []
    
    try:
        for url_index, url in enumerate(my_urls):
            # Check for pause before starting
            while check_pause_flag(output_dir):
                current_status = {
                    'rank': rank,
                    'current_url': url,
                    'completed': results,
                    'status': 'paused'
                }
                write_status(status_file, current_status)
                time.sleep(1)
            
            # Update status to "downloading"
            current_status = {
                'rank': rank,
                'current_url': url,
                'completed': results,
                'status': 'downloading',
                'progress': f"{url_index + 1}/{len(my_urls)}"
            }
            write_status(status_file, current_status)
            
            print(f"[Rank {rank}] Starting download {url_index + 1}/{len(my_urls)}: {url}")
            
            # Download with timing
            start_time = time.time()
            res = download_video(url, output_dir, video_quality, max_retries)
            res['time'] = time.time() - start_time
            res['rank'] = rank
            
            results.append(res)
            
            # Log result
            if res['status'] == 'success':
                print(f"[Rank {rank}] ✓ Success: {res['title']} ({res['time']:.2f}s, {res['attempts']} attempt(s))")
            else:
                print(f"[Rank {rank}] ✗ Failed: {url} - {res.get('error', 'Unknown error')} ({res['attempts']} attempt(s))", file=sys.stderr)
            
            # Update status with completed download
            current_status = {
                'rank': rank,
                'current_url': None,
                'completed': results,
                'status': 'idle',
                'progress': f"{url_index + 1}/{len(my_urls)}"
            }
            write_status(status_file, current_status)
            
            # Small delay to prevent overwhelming the system
            time.sleep(0.5)

    except KeyboardInterrupt:
        print(f"[Rank {rank}] Interrupted by user", file=sys.stderr)
    except Exception as e:
        print(f"[Rank {rank}] Unexpected error: {e}", file=sys.stderr)
    finally:
        # Final status update
        final_status = {
            'rank': rank,
            'current_url': None,
            'completed': results,
            'status': 'finished'
        }
        write_status(status_file, final_status)
        
        # Synchronize all ranks
        try:
            comm.Barrier()
            
            if rank == 0:
                # Collect statistics
                total_success = sum(1 for r in results if r['status'] == 'success')
                total_failed = sum(1 for r in results if r['status'] == 'error')
                
                print(f"\n[Master] ==================== SUMMARY ====================")
                print(f"[Master] Total URLs: {len(urls)}")
                print(f"[Master] Successful: {total_success}")
                print(f"[Master] Failed: {total_failed}")
                print(f"[Master] Downloads completed successfully!")
                
        except Exception as e:
            print(f"[Rank {rank}] Barrier or final sync failed: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()