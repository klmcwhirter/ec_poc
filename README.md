# ec_poc
POC for future project

## Set up

Install PDM: https://pdm-project.org/latest/#installation

`pdm install_dev`

## Run app

`pdm start` [options]

## Run tests

> Different tests will be skipped depending on whether the session has root privileges or not, and which Optimus mode the system is in.

`pdm test`

## Run tests with coverage report

> Different tests will be skipped depending on whether the session has root privileges or not, and which Optimus mode the system is in.

`pdm cov`

## Other scripts

`pdm clean`

`pdm create_venv`
