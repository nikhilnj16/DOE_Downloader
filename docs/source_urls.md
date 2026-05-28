# Source URLs

All source URLs are organized below by state and data category.  
Files are downloaded to `data/{state}/raw/{category}/` and cleaned outputs go to `data/{state}/cleaned/{category}/`.

---

## Nevada

| Category | URL | Description |
|---|---|---|
| Test Scores | https://nevadareportcard.nv.gov/DI/DownloadData | Nevada Report Card download portal — SBAC/CRT achievement data |
| Test Scores | https://doe.nv.gov/Stats_Data/Statewide_Data/ | NDE Statewide Data index page — links to assessment Excel workbooks |
| Test Scores | https://doe.nv.gov/Stats_Data/Statewide_Data/Test_Results/ | NDE Test Results subdirectory — annual CRT/SBAC result files |
| Financials | https://doe.nv.gov/Finance_Administration/ | NDE Finance Administration landing page |
| Financials | https://doe.nv.gov/Finance_Administration/Financial_Reports/ | Annual district financial report workbooks |
| Financials | https://doe.nv.gov/Finance_Administration/Per_Pupil_Expenditure/ | Per-pupil expenditure reports by district and year |
| Teacher Records | https://doe.nv.gov/Stats_Data/Statewide_Data/Educator_Data/ | Licensed educator counts, experience, and assignment area |
| Teacher Records | https://doe.nv.gov/Licensing/Statistics/ | NDE Licensing statistics — annual summary PDFs |
| Enrollment | https://doe.nv.gov/Stats_Data/Statewide_Data/Enrollment/ | Enrollment by grade, school, and district |
| Enrollment | https://nevadareportcard.nv.gov/DI/DownloadData | Nevada Report Card — enrollment download portal |
| Suspensions | https://doe.nv.gov/Stats_Data/Statewide_Data/Discipline/ | Discipline data: ISS, OSS, expulsions by school and subgroup |
| Suspensions | https://nevadareportcard.nv.gov/DI/DownloadData | Nevada Report Card — discipline download portal |

---

## Massachusetts

| Category | URL | Description |
|---|---|---|
| Test Scores | https://www.doe.mass.edu/mcas/results.html | MCAS results landing page with links to Excel/CSV downloads |
| Test Scores | https://profiles.doe.mass.edu/statereport/mcas.aspx | DESE State Report — MCAS achievement by school and district |
| Test Scores | https://profiles.doe.mass.edu/statereport/sat.aspx | DESE State Report — SAT and AP participation and scores |
| Financials | https://www.doe.mass.edu/finance/statistics/ | DESE finance statistics — per-pupil expenditure Excel workbooks |
| Financials | https://profiles.doe.mass.edu/statereport/finance.aspx | DESE State Report — district financial summary |
| Teacher Records | https://profiles.doe.mass.edu/statereport/teacherdata.aspx | DESE State Report — educator counts, FTEs, experience |
| Teacher Records | https://profiles.doe.mass.edu/statereport/teacherlicensure.aspx | DESE State Report — educator licensure status by district |
| Enrollment | https://www.doe.mass.edu/infoservices/reports/enroll/ | DESE enrollment reports — historical Excel workbooks by year |
| Enrollment | https://profiles.doe.mass.edu/statereport/enrollment.aspx | DESE State Report — enrollment by grade, race/ethnicity, subgroup |
| Suspensions | https://profiles.doe.mass.edu/statereport/suspensions.aspx | DESE State Report — out-of-school suspension rates by district |
| Suspensions | https://profiles.doe.mass.edu/statereport/inschoolsuspensions.aspx | DESE State Report — in-school suspension rates by district |

---

## Notes on Site Access

- **Nevada Report Card** (`nevadareportcard.nv.gov/DI/DownloadData`): May require AJAX POST parameters to select report type, year, and aggregation level. Inspect browser Network traffic to identify required form fields.
- **DESE Profiles** (`profiles.doe.mass.edu/statereport/`): Pages render HTML tables and often include an "Export to Excel" link. Check the page source or Network tab for the export endpoint.
- **Static listing pages** (NDE `doe.nv.gov/Stats_Data/`): Parse the HTML with BeautifulSoup to find `<a href>` links pointing to `.xlsx`, `.csv`, or `.pdf` files.
