import os
import requests
import time
from datetime import datetime, timedelta
import urllib.parse

def clean_text(text):
    """Remove extra whitespaces and newlines."""
    if not text:
        return ""
    return " ".join(text.split())

def query_europe_pmc(query_str, max_results=100):
    """
    Query Europe PMC API for preprints.
    This is highly efficient for historical searches as it supports server-side keywords.
    """
    papers = []
    cursor_mark = "*"
    batch_size = 50
    
    print(f"[*] Querying Europe PMC with query: {query_str}")
    headers = {"User-Agent": "LiteratureIntegrator/1.0 (steven955348@gmail.com)"}
    
    while len(papers) < max_results:
        encoded_query = urllib.parse.quote(query_str)
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={encoded_query}&format=json&pageSize={batch_size}&cursorMark={cursor_mark}"
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                print(f"[!] Europe PMC API returned status code: {response.status_code}")
                break
                
            data = response.json()
            results = data.get("resultList", {}).get("result", [])
            if not results:
                break
                
            for res in results:
                # We only want bioRxiv / medRxiv preprints
                comment_in = res.get("commentIn", "")
                journal = res.get("journalTitle", "").lower()
                book = res.get("bookOrForumType", "").lower()
                
                is_biorxiv = "biorxiv" in comment_in.lower() or "biorxiv" in journal or "biorxiv" in book
                is_medrxiv = "medrxiv" in comment_in.lower() or "medrxiv" in journal or "medrxiv" in book
                
                # Check DOI is present
                doi = res.get("doi")
                if not doi:
                    continue
                    
                source = "biorxiv" if is_biorxiv else ("medrxiv" if is_medrxiv else None)
                if not source:
                    # Default fallback: if it's preprint and EPMC says preprint
                    if res.get("pubType") == "preprint":
                        # Assume bioRxiv as default preprint source unless medRxiv is in text
                        abstract = res.get("abstractText", "").lower()
                        title = res.get("title", "").lower()
                        if "medrxiv" in abstract or "medrxiv" in title:
                            source = "medrxiv"
                        else:
                            source = "biorxiv"
                    else:
                        continue
                
                paper_id = doi
                title = clean_text(res.get("title", ""))
                authors = res.get("authorString", "")
                published_date = res.get("firstPublicationDate", "") # YYYY-MM-DD
                summary = clean_text(res.get("abstractText", ""))
                url = f"https://doi.org/{doi}"
                
                papers.append({
                    "paper_id": paper_id,
                    "title": title,
                    "authors": authors,
                    "published_date": published_date,
                    "summary": summary,
                    "url": url,
                    "source": source
                })
                
            # Next cursor
            next_cursor = data.get("nextCursorMark")
            if cursor_mark == next_cursor or not next_cursor:
                break
            cursor_mark = next_cursor
            
            # Rate limit compliance
            time.sleep(1)
            
        except Exception as e:
            print(f"[!] Error querying Europe PMC: {e}")
            break
            
    return papers[:max_results]

def get_biorxiv_daily_papers(server="biorxiv", days=3):
    """
    Fetch raw papers from the bioRxiv/medRxiv direct API for the last N days.
    Does not support server-side keywords; returns all papers for the date range.
    """
    papers = []
    today = datetime.today()
    start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")
    
    print(f"[*] Querying direct {server} API from {start_date} to {end_date}...")
    cursor = 0
    headers = {"User-Agent": "LiteratureIntegrator/1.0 (steven955348@gmail.com)"}
    
    while True:
        url = f"https://api.biorxiv.org/details/{server}/{start_date}/{end_date}/{cursor}"
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                print(f"[!] bioRxiv API returned status code {response.status_code}")
                break
                
            data = response.json()
            messages = data.get("messages", [])
            
            # Check for API errors
            if messages and "status" in messages[0] and "no papers found" in messages[0]["status"]:
                break
                
            collection = data.get("collection", [])
            if not collection:
                break
                
            for item in collection:
                doi = item.get("doi")
                if not doi: continue
                
                title = clean_text(item.get("title", ""))
                authors = item.get("authors", "")
                published_date = item.get("date", "")
                summary = clean_text(item.get("abstract", ""))
                url = f"https://www.biorxiv.org/content/{doi}v1" if server == "biorxiv" else f"https://www.medrxiv.org/content/{doi}v1"
                
                papers.append({
                    "paper_id": doi,
                    "title": title,
                    "authors": authors,
                    "published_date": published_date,
                    "summary": summary,
                    "url": url,
                    "source": server
                })
                
            # If we received less than 100 results, we reached the end
            if len(collection) < 100:
                break
                
            cursor += 100
            time.sleep(1) # complying with rate limit
            
        except Exception as e:
            print(f"[!] Error querying direct {server} API: {e}")
            break
            
    return papers

def filter_papers_local(papers):
    """Filter preprints locally using Biotech AND AI keyword intersection."""
    biotech_keywords = ["cancer vaccine", "drug", "neoantigen", "immunotherapy", "therapeutic", "docking", "ligand", "protein binding"]
    ai_keywords = ["machine learning", "deep learning", "artificial intelligence", "natural language processing", "neural network", "transformer", "language model", "llm"]
    
    filtered = []
    for paper in papers:
        text = (paper["title"] + " " + paper["summary"]).lower()
        
        # Check biotech keyword
        has_biotech = any(kw in text for kw in biotech_keywords)
        # Check AI keyword
        has_ai = any(kw in text for kw in ai_keywords)
        
        if has_biotech and has_ai:
            filtered.append(paper)
            
    return filtered

def fetch_biorxiv_papers(years_list=None, max_results=100, daily_mode=False):
    """Unified entry point for retrieving bioRxiv and medRxiv papers."""
    if daily_mode:
        print("[*] Running bioRxiv/medRxiv Daily Crawler...")
        # Get raw papers for the last 3 days
        biorxiv_raw = get_biotech_ai_query_direct("biorxiv", days=3)
        medrxiv_raw = get_biotech_ai_query_direct("medrxiv", days=3)
        
        all_raw = biorxiv_raw + medrxiv_raw
        filtered = filter_papers_local(all_raw)
        
        print(f"[*] bioRxiv/medRxiv Daily Crawler found {len(filtered)} papers after local filtering.")
        return filtered
    else:
        # Build query for Europe PMC
        # query = SRC:PPR AND (cancer vaccine OR drug OR neoantigen) AND (machine learning OR deep learning OR artificial intelligence OR natural language processing)
        biotech_query = '(cancer vaccine OR drug OR neoantigen OR immunotherapy)'
        ai_query = '(machine learning OR deep learning OR "artificial intelligence" OR "natural language processing" OR transformer OR "language model")'
        
        # Build year bounds
        if years_list:
            min_year = min(years_list)
            max_year = max(years_list)
            date_query = f"FIRST_PDATE:[{min_year}-01-01 TO {max_year}-12-31]"
        else:
            date_query = "FIRST_PDATE:[2020-01-01 TO 2026-12-31]"
            
        full_query = f"SRC:PPR AND {biotech_query} AND {ai_query} AND {date_query}"
        
        papers = query_europe_pmc(full_query, max_results=max_results)
        print(f"[*] bioRxiv/medRxiv Historical Crawler retrieved {len(papers)} papers total.")
        return papers

# Internal helper for daily mode
def get_biotech_ai_query_direct(server, days=3):
    return get_biorxiv_daily_papers(server, days)

if __name__ == "__main__":
    # Test query
    test_papers = fetch_biorxiv_papers(years_list=["2025", "2026"], max_results=5)
    print(f"[*] Test retrieved {len(test_papers)} preprints:")
    for p in test_papers:
        print(f"  - [{p['published_date']}] {p['title']} ({p['source']}: {p['paper_id']})")
