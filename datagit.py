import csv
import requests

class DatagitCrawler:
    """Datagit: Multi-organization GitHub repository data crawler."""
    
    def __init__(self, token=None):
        self.base_url = "https://api.github.com"
        self.headers = {"Accept": "application/vnd.github+json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def fetch_repositories(self, target_name):
        """Fetches public repositories for a GitHub organization."""
        url = f"{self.base_url}/orgs/{target_name}/repos"
        repos_data = []
        page = 1
        
        print(f"[*] Crawling repositories for organization: '{target_name}'...")
        
        while True:
            params = {"per_page": 100, "page": page}
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 404:
                print(f"[!] Error: Organization '{target_name}' not found.")
                break
            elif response.status_code != 200:
                print(f"[!] Error: Failed to fetch data (Status code: {response.status_code})")
                break
                
            page_data = response.json()
            if not page_data or len(page_data) == 0:
                break
                
            for repo in page_data:
                repos_data.append({
                    "Organization": target_name,
                    "Name": repo.get("name"),
                    "Description": repo.get("description"),
                    "Language": repo.get("language"),
                    "Stars": repo.get("stargazers_count"),
                    "Forks": repo.get("forks_count"),
                    "Open Issues": repo.get("open_issues_count"),
                    "URL": repo.get("html_url")
                })
                
            page += 1
            
        print(f"[+] Found {len(repos_data)} repositories for {target_name}.")
        return repos_data

    def save_to_csv(self, data, filename="ai_repos_dataset.csv"):
        """Saves combined repository data to a single CSV file."""
        if not data:
            print("[!] No repository data to save.")
            return
            
        keys = data[0].keys()
        with open(filename, mode="w", newline="", encoding="utf-8") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
            
        print(f"[+] Success! Saved a total of {len(data)} repositories to {filename}")

if __name__ == "__main__":
    # Target AI organizations for your project
    TARGETS = ["google", "anthropics", "GoogleCloudPlatform"]
    
    crawler = DatagitCrawler()
    all_repositories = []
    
    for target in TARGETS:
        repos = crawler.fetch_repositories(target)
        all_repositories.extend(repos)
        
    if all_repositories:
        crawler.save_to_csv(all_repositories, filename="ai_repos_dataset.csv")