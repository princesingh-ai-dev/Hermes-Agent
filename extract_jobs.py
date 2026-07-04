import re
import html
import json

with open('/tmp/internshala_jobs.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove script and style elements
content_clean = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
content_clean = re.sub(r'<style[^>]*>.*?</style>', '', content_clean, flags=re.DOTALL)

# Find all h2 headings with links (job titles)
# Pattern 1: <h2>...<a href="/job/...">Title</a>...</h2>
job_blocks = re.findall(r'<h2[^>]*>(.*?)</h2>', content_clean, re.DOTALL)

print("=== JOB LISTINGS FROM INTERNSHALA ===")
jobs = []
for block in job_blocks:
    # Extract job title
    title_match = re.search(r'<a[^>]*href="(/job/[^"]*)"[^>]*>(.*?)</a>', block, re.DOTALL)
    if title_match:
        title = html.unescape(re.sub(r'<[^>]+>', '', title_match.group(2)).strip())
        link = 'https://internshala.com' + title_match.group(1)
        jobs.append({'title': title, 'link': link})
        print(f"Title: {title}")
        print(f"Link: {link}")
        print("---")

print(f"\n=== Total job entries found: {len(jobs)} ===")

# Also list all companies mentioned
company_matches = re.findall(r'<p[^>]*class="[^"]*company-name[^"]*"[^>]*>(.*?)</p>', content_clean, re.DOTALL)
print(f"\n=== Company mentions: {len(company_matches)} ===")
for c in company_matches[:20]:
    c_clean = html.unescape(re.sub(r'<[^>]+>', '', c).strip())
    if c_clean:
        print(c_clean)
