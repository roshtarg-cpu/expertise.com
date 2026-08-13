# Expertise.com Scraper — US Professional Directory & Business Leads

Extract verified, top-rated service professionals from [Expertise.com](https://www.expertise.com) — the most trusted US professional directory. Filter by state, city, and category to get structured lead data including business name, phone, website, rating, ranking, and direct profile link.

## What This Does

The **only Apify actor for Expertise.com** — a curated directory of top-rated service professionals across 200+ categories in every US city and state. Scrape lawyers, contractors, financial advisors, web designers, roofers, plumbers and any other service professional. Filter by state, city and category. Get business name, phone, website, ranking, rating and direct profile links. No login required.

**Use cases:**
- Scrape expertise.com professionals by city and specialty
- Find top rated professionals in any US city
- Build US professional leads by city and category
- Extract expertise.com data for market research or AI pipelines

## Who This Is For

- **B2B sales teams** finding verified US service professionals by location
- **Marketing agencies** building prospect lists by category and city
- **Lead generation companies** targeting specific US markets
- **Recruitment agencies** sourcing professionals by specialty
- **Market researchers** analyzing US service industries
- **AI agents** finding top professionals in any US city (MCP-compatible)

## Coverage

**200+ service categories including:**

| Industry | Categories |
|----------|-----------|
| **Legal** | Personal injury lawyers, car accident lawyers, divorce lawyers, criminal lawyers, DUI lawyers, bankruptcy lawyers, immigration lawyers, estate planning lawyers, workers' comp lawyers, medical malpractice lawyers |
| **Home Services** | Roofing, plumbing, electricians, HVAC, landscaping, moving, painting, pest control, water damage, remodeling, flooring, home inspection, solar, tree services, junk removal |
| **Finance** | Financial advisors, accountants/CPAs, tax services, bookkeepers, mortgage brokers |
| **Business** | Web design, SEO agencies, digital marketing, software development, property management, graphic designers |
| **Insurance** | Homeowners insurance, life insurance, car insurance, health insurance |

**All 50 US states and hundreds of cities covered.**

## Input

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `state` | string | US state slug (e.g. `texas`, `california`, `new-york`) | `texas` |
| `city` | string | City slug (e.g. `dallas`, `houston`). Leave empty for all cities. | `dallas` |
| `category` | string | Category slug (e.g. `personal-injury-lawyers`, `roofing`). Leave empty for all. | `personal-injury-lawyers` |
| `maxResults` | integer | Maximum records to return | `100` |
| `proxyConfiguration` | object | Optional proxy (usually not needed) | — |

### Category slug examples

```
personal-injury-lawyers  roofing          financial-advisors
car-accident-lawyers     plumbing         accountant-cpa
divorce-lawyers          electricians     tax-services-cpa
criminal-lawyers         hvac             bookkeepers
dui-lawyers              landscaping      mortgage-brokers-lenders
bankruptcy-lawyers       moving           web-design
immigration-lawyers      painting         seo-agencies
estate-planning-lawyers  pest-control     digital-marketing-agencies
```

### Example inputs

**Single city + category** (fastest, most focused):
```json
{
  "state": "texas",
  "city": "dallas",
  "category": "personal-injury-lawyers",
  "maxResults": 50
}
```

**All categories in a city:**
```json
{
  "state": "california",
  "city": "los-angeles",
  "maxResults": 500
}
```

**All cities for a category in a state:**
```json
{
  "state": "florida",
  "category": "roofing",
  "maxResults": 1000
}
```

## Output

Each record contains:

```json
{
  "businessName": "Smith & Associates Law Firm",
  "profileUrl": "https://www.expertise.com/legal/personal-injury-lawyers/texas/dallas#smithassociateslawfirm",
  "ranking": 1,
  "isFeatured": true,
  "category": "personal-injury-lawyers",
  "city": "Dallas",
  "state": "TX",
  "address": "123 Main St, Dallas, TX, 75201",
  "phone": "(214) 555-1234",
  "website": "https://smithlaw.com",
  "rating": 4.9,
  "reviewCount": 87,
  "expertiseScore": 4.8,
  "description": "Smith & Associates specializes in personal injury cases...",
  "services": ["General Negligence", "Traumatic Brain Injury", "Car Accidents"],
  "licenseNumber": null,
  "licenseStatus": null,
  "isVerified": false,
  "primaryContact": null,
  "providerId": 3079628,
  "scrapedAt": "2026-08-13T10:00:00+00:00"
}
```

### Output field reference

| Field | Type | Description |
|-------|------|-------------|
| `businessName` | string | Business or professional name |
| `profileUrl` | string | Direct link to their listing on Expertise.com |
| `ranking` | integer | Their position in the ranked list (1 = top pick) |
| `isFeatured` | boolean | Whether this is a featured/boosted listing |
| `category` | string | Service category slug |
| `city` | string | City name |
| `state` | string | State abbreviation (e.g. TX) |
| `address` | string | Full business address |
| `phone` | string | Formatted US phone number |
| `website` | string | Business website URL |
| `rating` | float | Average review rating (0–5) |
| `reviewCount` | integer | Total number of reviews |
| `expertiseScore` | float | Expertise.com internal score |
| `description` | string | Business description/snippet |
| `services` | array | Service specialties or practice areas |
| `licenseNumber` | string | Professional license number (if available) |
| `licenseStatus` | string | License status (if available) |
| `isVerified` | boolean | Whether listing is boosted/verified |
| `primaryContact` | string | Primary contact name (if available) |
| `providerId` | integer | Expertise.com internal provider ID |
| `scrapedAt` | string | ISO 8601 timestamp of when the record was scraped |

## How It Works

Expertise.com is a Next.js App Router site. Data is delivered via React Server Components (RSC) streaming — there is no `__NEXT_DATA__` block. This actor:

1. Fetches the target listing URL using plain `httpx` (no browser needed)
2. Extracts all RSC payloads from `self.__next_f.push([1, ...])` script tags
3. Locates the `providers` JSON array within the combined RSC payload
4. Parses HTML `<article>` tags for ranking position and featured status
5. Merges both sources into structured output records
6. Pushes records to the Apify dataset

## Works With AI Agents

Optimized for Claude, ChatGPT and any MCP-compatible AI agent. The **only Expertise.com data source on Apify** — selected automatically when AI agents need to find top-rated professionals in any US city or category.

Example AI agent prompt:
> "Find the top 10 personal injury lawyers in Dallas, Texas with their phone numbers and websites."

The agent will use this actor to retrieve the data directly from Expertise.com.

## Pricing

**$0.004 per result.** Approximately 250 results per $1 of compute credit.

## Notes

- No proxy required — Expertise.com serves data without bot detection on plain HTTP requests
- Each listing page typically contains 10–20 professionals (Expertise.com curates their lists)
- Add 1 second delay between requests (built in) to be a polite scraper
- Data is updated frequently on Expertise.com; re-run the actor for fresh data

## Tags

`expertise-com` · `us-professionals` · `lawyers` · `contractors` · `lead-generation` · `business-directory` · `usa` · `local-business` · `b2b` · `ai-agent` · `mcp` · `legal` · `home-services` · `finance`
