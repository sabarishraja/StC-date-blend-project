# StC Data Platform — Question Playbook

A reference of every useful question the team can ask the platform. Copy any line into the question box on the dashboard. Questions are grouped by intent and the data source they primarily rely on.

> **Data coverage reminder**
> - **GA4** (`ga4_page_metrics`) — ~12 months of traffic, sessions, users, engagement, source/medium, landing pages
> - **GSC** (`gsc_queries`, `gsc_pages`) — ~16 months of Google search impressions, clicks, CTR, ranking position
> - **Meilisearch** (`ms_top_searches`, `ms_no_results`, `ms_countries`) — ~90 days of on-site search behavior
> - **Fullstory** (`fs_page_metrics`) — ~90 days of engagement quality (scroll depth, active time, rage/dead clicks)

---

## 1. Traffic & Audience (GA4)

### Volume and trends
- How many sessions did we get in the last 30 days?
- What was our total user count last month compared to the month before?
- Show me the daily sessions trend for the last 90 days.
- How many new users vs. returning users did we have last week?
- Which day of the week gets the most traffic on average?
- Has traffic grown or declined month over month over the last 6 months?
- What was our peak traffic day in the last 90 days and how many sessions did we get?

### Top pages
- What are the top 10 most visited pages in the last 30 days?
- Which pages had the most screenpage views last week?
- Which landing pages bring in the most new users?
- What are the top 5 lesson plan pages by sessions in the last 90 days?
- Which resource pages have the highest engagement time?
- Show me the top 20 pages with their bounce rate.
- Which pages get less than 10 sessions a month but exist in our content library?

### Traffic sources
- Where does our traffic come from? Break down by source/medium for the last 30 days.
- How much of our traffic is organic search vs. direct vs. referral vs. social?
- Which referral source has the highest engagement time?
- Has organic traffic grown over the last 6 months?
- Which source/medium has the best engaged-session rate?
- Which sources send the most new users vs. returning users?

### Engagement quality
- What is our overall bounce rate trend over the last 90 days?
- Which pages have the worst bounce rate (above 70%) with significant traffic?
- What is the average engagement time per session?
- Which pages have the highest engagement time per session?
- Which landing pages have the lowest engaged-session ratio?

---

## 2. SEO Performance (Google Search Console)

### Rankings and visibility
- What are our top 20 search queries by impressions in the last 30 days?
- Which queries do we rank #1 for?
- Which queries do we rank for in positions 4–10 (page 1, but not top)?
- Which queries are stuck on page 2 (positions 11–20) with high impressions?
- What is our average ranking position trend over the last 90 days?
- Which queries lost ranking position over the last 30 days vs. the previous 30?
- Which queries are gaining position month over month?

### Click-through performance
- Which pages get the most Google clicks in the last 30 days?
- Which queries have the most clicks?
- What is our overall CTR trend over time?
- Which queries have high impressions but a CTR below 1%? (low-hanging fruit for title/meta rewrites)
- Which pages rank in the top 5 but have a CTR below their position's expected rate?
- Which queries get clicks but rank below position 10?

### Content opportunities
- What are our top SEO opportunities — queries with impressions > 1000 but clicks < 50?
- Which queries do we appear for that we don't have dedicated pages targeting?
- Which pages have high impressions but low clicks?
- Which countries send us the most search traffic?
- Mobile vs. desktop — where do we get the most search clicks?
- Which devices have the highest CTR for our top queries?

---

## 3. On-Site Search Behavior (Meilisearch)

### What users want
- What are the top 20 most-searched terms on the site in the last 30 days?
- What are users searching for this week?
- Has the volume of on-site searches grown or declined over the last 90 days?
- Which search terms are trending up week over week?
- What did users search for during Earth Week (April 14–22)?

### Content gaps — searches with no results
- What are the top content gaps — searches with no results in the last 30 days?
- Which no-results searches are repeated by multiple users? (priority gaps)
- What no-results searches have grown over the last 30 days?
- Are there no-results searches that match topics we cover but under different names? (taxonomy issues)
- Which no-results queries should we prioritize creating content for?

### Geographic search patterns
- Which countries do our on-site searchers come from?
- Are international users searching for different topics than US users?
- Which countries drive the most search volume per session?

### Search vs. site content alignment
- Are users finding our top-performing pages via search, or via navigation?
- Which top-searched terms have matching pages with low traffic? (discoverability issues)

---

## 4. User Engagement Quality (Fullstory)

### Page-level engagement
- Which pages have the highest average scroll depth?
- Which pages have the lowest scroll depth (users bouncing without reading)?
- What is the average active time per page for our top 20 pages?
- Which pages have an average active time under 30 seconds?

### Frustration signals
- Which pages have the most rage clicks in the last 30 days?
- Which pages have the most dead clicks (clicks on non-clickable elements)?
- Are rage clicks concentrated on specific page templates (lesson plans, articles, search)?
- Has the rate of rage clicks per session changed over the last 90 days?

### Session quality
- Which pages have the most sessions but the lowest active time? (red flag for content quality)
- Which pages have high active time and high scroll depth? (our strongest content)

---

## 5. Cross-Source / Blended Questions

These questions join two or more data sources and answer the most important strategic questions.

### Search demand vs. site supply
- Which on-site search terms also appear in Google Search Console queries? (validated demand)
- Which Google search queries bringing us impressions match terms users also search for on-site?
- Are there topics users search for on-site (via Meilisearch) that we don't rank for on Google?

### Traffic vs. engagement
- Which top GA4 pages have the worst Fullstory scroll depth? (high traffic, low quality)
- Which pages have great Fullstory engagement but low GA4 traffic? (hidden gems to promote)
- Which top SEO landing pages have rage clicks?

### Lifecycle of a topic
- For the query "climate change," what are the GSC impressions, GA4 sessions on the matching page, and Fullstory engagement metrics?
- Show me the full funnel for our top 10 SEO pages: impressions → clicks → sessions → scroll depth → active time.
- For our top 10 on-site search terms, do we rank for the same terms in Google?

### Content audit signals
- Which lesson plan pages have low GA4 traffic AND high GSC impressions? (SEO opportunities)
- Which pages get organic search traffic but have a high bounce rate in GA4?
- Which pages users land on from search and then immediately bounce (high entrance + high bounce)?

---

## 6. Strategy Questions (Pre-Built Insights)

These are the questions the dashboard auto-answers on every page load:

- **Traffic trend** — Is week-over-week traffic up or down, and by how much?
- **Top pages** — What are the top 5 pages by sessions this week?
- **Top searches** — What did users search for most on-site this week?
- **Content gaps** — What did users search for that returned no results this week?
- **SEO opportunities** — Which queries get 50+ impressions but few clicks this week?

---

## 7. Seasonal and Campaign Questions

- How did traffic perform during Earth Day week compared to the rest of April?
- Which lesson plans saw a spike during back-to-school season (August–September)?
- Did our [campaign name] launch on [date] move traffic to the targeted pages?
- Which evergreen pages stay strong every month vs. seasonal pages?
- What were the top 10 pages during the last academic semester?

---

## 8. Tips for Asking Good Questions

- **Be specific about time** — "last 30 days" beats "recently"
- **Name the metric** — "sessions" or "clicks" or "scroll depth," not just "performance"
- **Combine sources for strategy** — "which pages have high impressions but low engagement time" is more actionable than either source alone
- **Ask for limits** — "top 10," "top 20" — keeps answers focused
- **Start broad, then drill in** — first ask "what are our top SEO opportunities?" then "tell me more about the query 'is pluto a planet'"

---

## 9. Questions to Avoid (Won't Work Well)

- ❌ Questions about individual users, sessions, or PII — not in our schema
- ❌ Questions requiring data older than 12 months (GA4) or 90 days (Meilisearch/Fullstory)
- ❌ Questions about revenue, conversions, or ecommerce — not tracked
- ❌ Real-time questions ("what's happening right now") — data syncs daily, not live
- ❌ Predictive questions ("what will traffic be next month") — the platform reports, it doesn't forecast
