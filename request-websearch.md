search endpoint: https://api.deutschlandgpt.de/v2/search
docs: https://dialog.deutschlandgpt.de/docs/en/platform-api/createWebSearch

auth via `Authorization` header:

// the openai key is for the dgpt api actually
Authorization: "Bearer ${OPENAI_API_KEY}"

basic request example:

```json
{
  "query": "Tech news from today"
}
```

response:

```json
{
  "object": "web_search",
  "model": "web-search",
  "query": "Tech news from today",
  "data": [
    {
      "title": "Reuters Tech News | Today's Latest Technology News | Reuters",
      "url": "https://www.reuters.com/technology/",
      "description": "Britain&#x27;s threat to intervene in the $110 billion Paramount-Warner deal could be less about blocking the transaction than extracting commitments on UK news, children&#x27;s TV and investment, with the cost of any delay increasing the ​government&#x27;s leverage. ... Hiring for AI roles within India&#x27;s IT sector outpaced overall recruitment within the industry last month, a ​survey showed on Friday, indicating a push from companies ‌to reorient themselves in the face of evolving technology.",
      "age": "4 days ago"
    },
    {
      "title": "Technology News",
      "url": "https://www.cnbc.com/technology/",
      "description": "Trump threatens EU with &#x27;substantial TARIFF&#x27; for &#x27;ROBBING&#x27; U.S. tech giants ... Saudi military strikes Houthi targets in Yemen after the Iran-backed militia attacked Red Sea shipping ...",
      "age": "2 days ago"
    },
    {
      "title": "Tech | CNN Business",
      "url": "https://www.cnn.com/business/tech",
      "description": "Latest Market News · Trump bombed at the White House Correspondents’ Dinner — and proved its point · Paramount agrees to delay Warner Bros. Discovery takeover for months · Trump’s appetite for tariffs never faded. His next moves could reshape trade · Hot Stocks · Something isn&#x27;t loading properly. Please check back later. Ad Feedback · SeongJoon Cho/Bloomberg/Getty Images · Tech titan’s ex-wife fails to win greater share of AI boom in decade-long ‘divorce of the century’ ·",
      "age": "2 days ago"
    },
    {
      "title": "WIRED - The Latest in Technology, Science, Culture and Business | WIRED",
      "url": "https://www.wired.com/",
      "description": "WIRED commissioned five stories about decommissioning, from EVs and internet cables to supercomputers and space stations. ... Ice hockey, curling, influencers—the 2026 Winter Olympics promise to be the most talked about Games in recent memory."
    },
    {
      "title": "Technology - The New York Times",
      "url": "https://www.nytimes.com/section/technology",
      "description": "Free apps from Google, Samsung and Apple can help you track your diet, exercise and well-being — and provide vital information during emergencies. By J. D. Biersdorfer ... The social platform that Meta once positioned as a rival to Elon Musk’s X now has 500 million monthly users. It increasingly resembles Reddit. ... CreditIan C. Bates for The New York Times · This Music Box Is a Ray of Hope for a Decadent Tech Industry",
      "age": "3 days ago"
    },
    {
      "title": "Google News - Technology - Latest",
      "url": "https://news.google.com/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&ceid=US%3Aen&gl=US",
      "description": "Samsung Galaxy Unpacked is almost here: Everything we expect from the July 22 event · 1 hour ago · By Alex Perry &amp; Timothy Beck Werth · The Verge · More · Samsung’s redesigned Z Fold 8 with a wide display just leaked · 3 days ago · By Stevie Bonifield · Samsung Global Newsroom · More · Samsung Introduces Flex Titanium Technology To Advance Foldable Displays ·"
    },
    {
      "title": "Tech | The Verge",
      "url": "https://www.theverge.com/tech",
      "description": "Today’s test was important for former trillionaire Elon Musk, with shares of Tesla and SpaceX declining by 18 and 7 percent this week, respectively. Update: Updated to note that the vehicle has launched. Meta just created a moderation nightmare for its smart glasses · ﻿Meta says it’s banning some content filmed with the company’s smart glasses from Instagram.",
      "age": "3 weeks ago"
    },
    {
      "title": "Technology: Latest Tech News Articles Today | AP News",
      "url": "https://apnews.com/technology",
      "description": "See All Newsletters ... OpenAI blamed a hacking event on its AI models going rogue. Here are some things to know · Mideast oil producers step up plans to bypass the Strait of Hormuz · OpenAI says rogue AI models broke free from human control.",
      "age": "1 week ago"
    },
    {
      "title": "Engadget | Technology News & Expert Reviews",
      "url": "https://www.engadget.com/",
      "description": "The extended pause will give time to hear cases for blocking the deal from states and the WGA. By Ian Carlos Campbell Read More ... While its display could be nicer, Alienware’s first budget gaming laptop feels like a welcome reprieve when practically all tech is more expensive.",
      "age": "7 hours ago"
    },
    {
      "title": "TechCrunch | Startup and Technology News",
      "url": "https://techcrunch.com/",
      "description": "TechCrunch | Reporting on the business of technology, startups, venture capital funding, and Silicon Valley"
    }
  ],
  "usage": {
    "queries": 1
  }
}
```

let's switch from brave to this, and remove brave completely
