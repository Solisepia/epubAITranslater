param(
  [string]$Input = "tests/fixtures/fixture_basic.epub",
  [string]$Output = "tests/out/fixture_basic.translated.epub"
)

$env:PYTHONPATH = "src"
python -m epub2zh_faithful.cli $Input -o $Output --provider mock --revise-provider none --cache tests/out/example.sqlite --config config.yaml --termbase termbase.yaml --resume
