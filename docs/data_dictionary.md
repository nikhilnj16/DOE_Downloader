# Data Dictionary

This document describes the expected columns present in cleaned output files
for each data category after the cleaner scripts have been run.

All cleaned files are saved to `data/{state}/cleaned/{category}/` as UTF-8 CSV files.
Two metadata columns are appended to every cleaned file:

| Column | Type | Description |
|---|---|---|
| `state` | string | State identifier: `"nevada"` or `"massachusetts"` |
| `source_file` | string | Original raw filename this row was derived from |

---

## Test Scores

Expected columns after cleaning (exact names depend on the source file schema):

| Column | Type | Description |
|---|---|---|
| `school_year` | string | Academic year, e.g. `"2022-2023"` |
| `district_code` | string | State-assigned district identifier |
| `district_name` | string | Full district name |
| `school_code` | string | State-assigned school identifier |
| `school_name` | string | Full school name |
| `subject` | string | Test subject: `ELA`, `Math`, `Science` |
| `grade` | string | Grade level tested, e.g. `"3"`, `"8"`, `"HS"` |
| `subgroup` | string | Student subgroup: `All Students`, `ELL`, `SWD`, etc. |
| `proficiency_level` | string | Performance band label |
| `percent_proficient` | string | % of students at or above proficiency |
| `count_tested` | string | Number of students tested |
| `state` | string | Metadata — state identifier |
| `source_file` | string | Metadata — raw source filename |

---

## Financials

| Column | Type | Description |
|---|---|---|
| `school_year` | string | Academic year |
| `district_code` | string | State-assigned district identifier |
| `district_name` | string | Full district name |
| `per_pupil_expenditure` | string | Total per-pupil expenditure (dollars, commas stripped) |
| `instructional_expenditure` | string | Expenditure on instruction per pupil |
| `administrative_expenditure` | string | Expenditure on administration per pupil |
| `total_expenditure` | string | Total district expenditure |
| `revenue_local` | string | Local revenue amount |
| `revenue_state` | string | State aid received |
| `revenue_federal` | string | Federal funds received |
| `state` | string | Metadata |
| `source_file` | string | Metadata |

---

## Teacher Records

| Column | Type | Description |
|---|---|---|
| `school_year` | string | Academic year |
| `district_code` | string | State-assigned district identifier |
| `district_name` | string | Full district name |
| `school_code` | string | School identifier (if school-level data) |
| `teacher_count` | string | Number of teachers (FTE or headcount) |
| `avg_years_experience` | string | Average years of teaching experience |
| `license_status` | string | Normalised license status (Title Case) |
| `assignment_area` | string | Subject/grade assignment area |
| `highly_qualified_pct` | string | Percentage of teachers meeting HQ criteria |
| `state` | string | Metadata |
| `source_file` | string | Metadata |

---

## Enrollment

| Column | Type | Description |
|---|---|---|
| `school_year` | string | Academic year |
| `district_code` | string | State-assigned district identifier |
| `district_name` | string | Full district name |
| `school_code` | string | School identifier |
| `school_name` | string | Full school name |
| `grade` | string | Grade level |
| `total_enrollment` | string | Total student count (commas stripped) |
| `race_ethnicity` | string | Racial/ethnic subgroup label |
| `gender` | string | Gender category |
| `ell_count` | string | English Language Learner headcount |
| `swd_count` | string | Students with Disabilities headcount |
| `state` | string | Metadata |
| `source_file` | string | Metadata |

---

## Suspensions / Discipline

| Column | Type | Description |
|---|---|---|
| `school_year` | string | Academic year |
| `district_code` | string | State-assigned district identifier |
| `district_name` | string | Full district name |
| `school_code` | string | School identifier |
| `school_name` | string | Full school name |
| `discipline_type` | string | Normalised type: `"In-School Suspension"`, `"Out-Of-School Suspension"`, `"Expulsion"` |
| `incident_count` | string | Number of discipline incidents |
| `student_count` | string | Number of unduplicated students receiving discipline |
| `subgroup` | string | Student subgroup |
| `suspension_rate` | string | Suspension rate (%) |
| `state` | string | Metadata |
| `source_file` | string | Metadata |

---

> **Note**: Because source files vary by year and agency, not every column listed above will be present in every cleaned file. The cleaner scripts standardise whatever columns exist in the source — they do not impute missing columns. Always check `df.columns` after loading a cleaned file.
