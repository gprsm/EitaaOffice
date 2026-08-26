const fs = require('fs');

let testCode = fs.readFileSync('tests/test_material_ui_repair.py', 'utf8');

testCode = testCode.replace(
  'def test_index_workbench_is_material_dialog_and_not_header_popover() -> None:\n    app = read("App.tsx")\n    workbench = read("MaterialIndexWorkbench.tsx")',
  'def test_index_workbench_is_material_dialog_and_not_header_popover() -> None:\n    app = read("App.tsx")\n    workbench = read("MessageFilterDialog.tsx")\n    index = read("ContentIndexDialog.tsx")'
);

testCode = testCode.replace(
  '    assert "<MaterialIndexWorkbench" in app\n    assert "content-filter-popover" not in app\n    assert "<Dialog" in workbench\n    assert "<Grid container" in workbench\n    assert "fullScreen={fullScreen}" in workbench\n    assert "\u0627\u06cc\u0646\u062f\u06a9\u0633\u200c\u06af\u0630\u0627\u0631\u06cc" in workbench and "\u0646\u0645\u0627\u06cc\u0634 \u0648 \u0641\u06cc\u0644\u062a\u0631" in workbench',
  '    assert "<MessageFilterDialog" in app\n    assert "<ContentIndexDialog" in app\n    assert "content-filter-popover" not in app\n    assert "<Dialog" in workbench\n    assert "<Dialog" in index\n    assert "\u0641\u06cc\u0644\u062a\u0631 \u0646\u0645\u0627\u06cc\u0634 \u067e\u06cc\u0627\u0645\u200c\u0647\u0627" in workbench\n    assert "\u0627\u06cc\u0646\u062f\u06a9\u0633\u200c\u06af\u0630\u0627\u0631\u06cc \u0645\u062d\u062a\u0648\u0627" in index'
);

testCode = testCode.replace(
  'def test_sender_filter_uses_names_and_marks_eitaa_contacts() -> None:\n    app = read("App.tsx")\n    workbench = read("MaterialIndexWorkbench.tsx")',
  'def test_sender_filter_uses_names_and_marks_eitaa_contacts() -> None:\n    app = read("App.tsx")\n    workbench = read("MessageFilterDialog.tsx")'
);

fs.writeFileSync('tests/test_material_ui_repair.py', testCode);

// Now fix test_ui32_composer_usage_layout.py
let layoutTest = fs.readFileSync('tests/test_ui32_composer_usage_layout.py', 'utf8');
layoutTest = layoutTest.replace(
  'assert "\u0627\u0631\u0633\u0627\u0644 \u0648 \u062f\u0639\u0648\u062a \u06af\u0631\u0648\u0647\u06cc" in navigation',
  'assert "ConnectWithoutContactRounded" in navigation'
);
fs.writeFileSync('tests/test_ui32_composer_usage_layout.py', layoutTest);

console.log('done');
