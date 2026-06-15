# Input Schema

## Accepted Source

Only accept a single Amazon reviews CSV or Excel file.

## Required Columns

The file must contain all of these columns:

- `Content`
- `Rating`
- `Date`
- `Helpful`
- `Verified Purchase`

Case-insensitive matching is allowed. Missing required columns are a hard stop.
`Name` / reviewer identity is optional; if absent, the preprocessor fills it
with `Unknown`.

Common alias columns are accepted, including:

- `Review Text`, `Review Body`, `Body` -> `Content`
- `Stars`, `Star Rating` -> `Rating`
- `Review Date` -> `Date`
- `Helpful Votes`, `Helpful Count` -> `Helpful`
- `Reviewer`, `Author`, `Reviewer Name` -> `Name`
- `Verified`, `Verified Buyer` -> `Verified Purchase`
- SellerSprite Chinese exports:
  - `内容` -> `Content`
  - `星级` -> `Rating`
  - `评论时间` -> `Date`
  - `赞同数` -> `Helpful`
  - `评论人` -> `Name`
  - `VP评论` -> `Verified Purchase`

SellerSprite-format exports are detected automatically. Because SellerSprite
review exports may be collected with a star-balanced sampling strategy, the
English report should include a method note warning that rating distribution may
represent the sampled mix rather than the product's natural Amazon rating
distribution.

## Validation Rules

- `Content` must be non-empty text after trimming.
- `Rating` must be coercible to numeric.
- Ratings outside 1-5 or non-numeric ratings are marked `invalid_rating` and
  excluded from analysis.
- `Date` must be parseable for trend analysis; invalid dates may remain null but should be counted.
- `Helpful` must be coercible to numeric.
- Invalid `Helpful` values are counted and treated as 0 for selection ranking.
- `Verified Purchase` must be preserved and normalized to a boolean. Only
  explicit verified values such as `Y`, `Yes`, `True`, `1`,
  `Verified Purchase`, or `Verified Buyer` count as verified.

## Preprocessing Expectations

- assign stable `review_id`
- deduplicate exact content duplicates
- remove trivial or unusable reviews
- normalize basic types
- record exclusion reasons
- mark whether each row is selected for analysis

## Cleaned XLSX Export

The cleaned XLSX should include these columns:

- `review_id`
- `Content`
- `Rating`
- `Date`
- `Helpful`
- `Name`
- `Verified Purchase`
- `verified_purchase_bool`
- `content_length`
- `is_duplicate`
- `is_trivial`
- `rating_invalid`
- `date_invalid`
- `helpful_invalid`
- `selected_for_analysis`
- `excluded_reason`
- `chunk_id`
- `quoted_in_report`

Recommended optional columns for later expansion:

- `content_normalized`
- `rating_numeric`
- `date_normalized`
- `helpful_numeric`
- `selection_bucket`
- `selection_rank`
- `persona_tags`
- `advantage_tags`
- `pain_point_tags`
- `llm_included`
