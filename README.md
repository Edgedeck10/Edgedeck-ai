# EdgeDeck
Mobile-first sports research dashboard for free GitHub Pages hosting.

## Deployment
Upload this directory, including .github/workflows/refresh.yml, to the main branch of Edgedeck10/Edgedeck-ai. In Settings → Pages choose GitHub Actions as Source. The initial push runs the refresh and deployment. If automatic Pages enablement fails, select GitHub Actions manually and rerun the workflow.

The workflow runs at 13:17 and 21:17 UTC daily: 8:17 AM / 4:17 PM Indiana time in winter, 9:17 AM / 5:17 PM in summer. Scheduled Actions can be delayed or disabled after repository inactivity. All storage is public repository JSON. No paid services, secrets, accounts, or odds API calls are required.

Required access: repository Contents write and Workflows write for uploading source and workflow files. Workflow runtime requests contents:write, pages:write and id-token:write. Initial Pages configuration may require repository administration access. GitHub Actions must be enabled.

## Scope
NBA, NFL, MLB, NHL, NCAAF and men's NCAAB moneyline baseline. ESPN public scoreboards supply schedules and final scores. Availability is not guaranteed. No live sportsbook prices, player props, injuries, spreads or totals are modeled. Fictional demo picks require an explicit button press.

Predictions are archived before start, graded after finals, and retained in data/history.json. Pending event dates are rechecked on later runs. Last 25 available past team results use Bayesian shrinkage with a home advantage prior. Calibration uses home-side residuals only, shrunk toward zero, to avoid complementary forecasts cancelling the adjustment. Brier score and settled counts are displayed. With no market prices, no verified edge or ROI is claimed. This is an unvalidated baseline; meaningful learning requires sustained history and further validation.

## Local use
Python 3.10+ with standard library: python pipeline.py. Serve this directory over HTTP to load dashboard JSON. No dependency installation required.

## Current deployment status
Prepared and locally checked. Repository writes returned HTTP 403 Resource not accessible by integration. No source files were uploaded and no published deployment was verified.
