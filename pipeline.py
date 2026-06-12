#!/usr/bin/env python3
"""Unified pipeline for WeChat articles (Steam discounts + thematic).

Usage:
    python3 pipeline.py scrape --appids 105600 --images path/to/images
    python3 pipeline.py build --state output/state.json
    python3 pipeline.py validate --state output/state.json
    python3 pipeline.py publish --state output/state.json
    python3 pipeline.py kpi --validation output/validation.json --state output/state.json
    python3 pipeline.py run --type thematic --state output/state.json

Steps are independent - each reads/writes JSON state files.
"""

import os, sys, json, argparse, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    parser = argparse.ArgumentParser(description="WeChat article pipeline")
    parser.add_argument("step", choices=["scrape", "build", "validate", "publish", "kpi", "run"], help="Pipeline step")
    parser.add_argument("--state", help="State JSON file path", default=None)
    parser.add_argument("--appids", nargs="+", help="Steam AppIDs to scrape", default=None)
    parser.add_argument("--images", help="Local image directory", default=None)
    parser.add_argument("--type", choices=["discount", "thematic"], default="discount")
    parser.add_argument("--validation", help="Validation report file for kpi step", default=None)
    parser.add_argument("--retry", action="store_true", help="Retry fix if BLOCKING found")
    parser.add_argument("--no-publish", action="store_true", help="Stop after validation, don't publish")
    
    args = parser.parse_args()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    step = args.step
    state_path = args.state or os.path.join(output_dir, f"state_{step}.json")
    
    if step == "scrape":
        # Scrape: download images, upload to CDN, generate HTML
        from terraria_scrape import main as scrape_main
        if args.type == "thematic":
            sys.exit(scrape_main(args.appids, args.images, state_path))
        else:
            # For discounts, use cron_digest.py
            cmd = [sys.executable, os.path.join(base_dir, "cron_digest.py")]
            result = subprocess.run(cmd)
            sys.exit(result.returncode)
            
    elif step == "validate":
        # Validate: check AppID, images, HTML structure
        from terraria_validate import main as validate_main
        if args.validation:
            sys.exit(validate_main(state_path, args.validation, args.type))
        else:
            print(f"Usage: python3 pipeline.py validate --state {state_path}")
            return 1
            
    elif step == "publish":
        # Publish: create WeChat draft
        from terraria_publish import main as publish_main
        sys.exit(publish_main(state_path, args.retry))
        
    elif step == "kpi":
        # KPI: calculate scores based on validation results
        from terraria_kpi import main as kpi_main
        if args.validation:
            sys.exit(kpi_main(state_path, args.validation))
        else:
            print(f"Usage: python3 pipeline.py kpi --state {state_path} --validation {args.validation}")
            return 1
            
    elif step == "run":
        # Full pipeline: scrape -> validate -> publish -> kpi
        print("Running full pipeline...")
        
        # Scrape
        print("Step 1/4: Scraping...")
        if args.type == "thematic":
            sys.exit(scrape_main(args.appids, args.images, state_path))
        else:
            cmd = [sys.executable, os.path.join(base_dir, "cron_digest.py")]
            result = subprocess.run(cmd)
            if result.returncode != 0:
                print("Scraping failed, stopping.")
                return 1
                
        # Validate
        print("Step 2/4: Validating...")
        val_file = os.path.join(output_dir, "validation.json")
        result = subprocess.run([sys.executable, os.path.join(base_dir, "terraria_validate.py"), 
                               state_path, val_file, args.type])
        if result.returncode != 0:
            print("Validation failed, stopping.")
            return 1
            
        if args.no_publish:
            print("Skipping publish (no-publish flag set)")
            return 0
            
        # Publish
        print("Step 3/4: Publishing...")
        result = subprocess.run([sys.executable, os.path.join(base_dir, "terraria_publish.py"), 
                               state_path, "--retry" if args.retry else ""])
        if result.returncode != 0:
            print("Publishing failed, stopping.")
            return 1
            
        # KPI
        print("Step 4/4: Computing KPI...")
        result = subprocess.run([sys.executable, os.path.join(base_dir, "terraria_kpi.py"), 
                               state_path, val_file])
        if result.returncode != 0:
            print("KPI computation failed, but article is already published.")
            return 0
            
        print("Pipeline complete!")
        return 0

if __name__ == "__main__":
    sys.exit(main())
