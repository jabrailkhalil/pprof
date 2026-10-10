import json
import sys
from pathlib import Path

name = sys.argv[1]
folder = Path(sys.argv[2])
negative = '--negative' in sys.argv
expected = {
    'pr-1032': ['TestComposeWithNamesThatNeedEscaping', 'TestComposeWithFilenamesWithBackslashes'],
    'pr-1033': ['TestProfileDetails'],
    'pr-1035': ['TestSamplingDetails', 'TestSamplingDetails/cpu', 'TestSamplingDetails/heap'],
}


def events(stem):
    return [json.loads(line) for line in (folder / f'{stem}.jsonl').read_text().splitlines() if line.strip()]


def outcomes(items):
    return {(item['Package'], item['Test']): item['Action'] for item in items
            if 'Test' in item and item['Action'] in ('pass', 'fail', 'skip')}


if negative:
    items = events('negative')
    results = outcomes(items)
    assert any(item['Action'] == 'fail' and 'Test' in item for item in items), 'No actual test failure'
    assert not any('build failed' in item.get('Output', '') for item in items), 'Compile failure is not a negative control'
    for test in expected[name]:
        assert any(key[1] == test and action == 'fail' for key, action in results.items()), (test, results)
    changed = (folder / 'negative-changed-files.txt').read_text().splitlines()
    allowed = {'browsertests/browser_test.go', 'internal/driver/webui_test.go',
               'internal/graph/dotgraph_test.go', 'internal/graph/testdata/compose7.dot',
               'internal/graph/testdata/compose_filename_backslash.dot'}
    assert changed and set(changed) <= allowed, changed
    summary = {'arm': name, 'negative_control': dict((key[1], value) for key, value in results.items()),
               'changed_test_files_only': changed}
    (folder / 'negative-summary.json').write_text(json.dumps(summary, indent=2))
else:
    root = events('root')
    browser = events('browser')
    summary = {'arm': name, 'modules': {}}
    for module, items in [('root', root), ('browser', browser)]:
        results = outcomes(items)
        failures = [item for item in items if item['Action'] == 'fail']
        assert not failures, failures
        package_pass = [item for item in items if item['Action'] == 'pass' and 'Test' not in item]
        assert results and package_pass, f'{module}: no actual tests'
        summary['modules'][module] = {'passed_test_and_subtest_events': sum(action == 'pass' for action in results.values()),
                                      'skipped_test_and_subtest_events': sum(action == 'skip' for action in results.values()),
                                      'passed_packages': len(package_pass)}
        if module == 'browser':
            assert all(action == 'pass' for action in results.values()), results
    if name in expected:
        combined = outcomes(root + browser)
        for test in expected[name]:
            assert any(key[1] == test and action == 'pass' for key, action in combined.items()), (test, combined)
        summary['required_regressions_passed'] = expected[name]
    (folder / 'summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary))
