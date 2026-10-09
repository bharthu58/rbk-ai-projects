import asyncio
import sys
from pathlib import Path

# Add parent directory to sys.path to allow imports from medium_ingest package
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent))

from medium_ingest.fetcher import MediumFetcher, ArticleMetadata

async def run_test():
    # 1. Configuration: Change this to a URL you want to test
    test_url = "https://medium.com/gitconnected/how-to-structure-claude-folder-for-maximum-efficiency-c26ef3f552ba" 
    meta = ArticleMetadata(url=test_url)
    
    print(f"--- Starting Medium Fetch Test ---")
    print(f"Target URL: {test_url}")
    print(f"Using profile: {Path.home() / '.medium_ingest_profile'}")

    # 2. Execution using the stealth logic in MediumFetcher
    async with MediumFetcher() as fetcher:
        try:
            html, enriched_meta = await fetcher.fetch_article(meta)
            
            # 3. Output results
            print("\nFetch successful!")
            print(f"Title:         {enriched_meta.title}")
            print(f"Author:        {enriched_meta.author}")
            print(f"Reading Time:  {enriched_meta.reading_time}")
            print(f"Published:     {enriched_meta.published_date}")
            print(f"Tags:          {', '.join(enriched_meta.tags)}")
            print(f"HTML Content:  {len(html)} chars")
            
            if "verify you are human" in html.lower():
                print("\nWARNING: Bot detection page detected in HTML output!")
            else:
                print("\nContent snippet (first 200 chars):")
                print(f"{html[:200]}...")

        except Exception as e:
            print(f"\nFetch failed with error: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())