import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import run as run_match
from scripts.bootstrap_labels import main as bootstrap_main

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PITCHDECKS_DIR = os.path.join(BASE_DIR, "data", "input", "pitchdecks")


def batch_process(pitchdecks_dir: str = PITCHDECKS_DIR):
    pdf_files = sorted(glob.glob(os.path.join(pitchdecks_dir, "*.pdf")))
    if not pdf_files:
        print(f"[batch] Không tìm thấy file PDF nào trong {pitchdecks_dir}")
        return

    for i, pdf_path in enumerate(pdf_files, 1):
        name = os.path.basename(pdf_path)
        try:
            run_match(pdf_path)
        except Exception as e:
            print(f"[batch]   Lỗi khi match {name}: {e}")
            continue
        try:
            bootstrap_main(reset_non_bootstrap=(i == 1))
        except Exception as e:
            print(f"[batch]   Lỗi khi bootstrap label cho {name}: {e}")
            continue
        print()



if __name__ == "__main__":
    batch_process()