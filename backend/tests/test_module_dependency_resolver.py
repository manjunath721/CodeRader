from app.analyzers.module_dependency_resolver import extract_external_libraries, resolve_module_dependencies


def test_resolves_python_dotted_import_to_module():
    modules = ["src/payment", "src/billing"]
    files = [("src/billing/invoice.py", "src/billing", ["src.payment.gateway"])]
    edges = resolve_module_dependencies(modules, files)
    assert len(edges) == 1
    assert edges[0].from_module_prefix == "src/billing"
    assert edges[0].to_module_prefix == "src/payment"


def test_resolves_relative_js_import_against_importing_file_directory():
    modules = ["src/payment", "src/billing", "src/checkout"]
    files = [("src/checkout/flow.js", "src/checkout", ["../billing/invoice"])]
    edges = resolve_module_dependencies(modules, files)
    assert len(edges) == 1
    assert edges[0].to_module_prefix == "src/billing"


def test_self_imports_are_excluded():
    modules = ["src/payment"]
    files = [("src/payment/a.py", "src/payment", ["src.payment.b"])]
    edges = resolve_module_dependencies(modules, files)
    assert edges == []


def test_external_package_imports_produce_no_edge():
    modules = ["src/payment"]
    files = [("src/payment/a.py", "src/payment", ["os", "react", "numpy"])]
    edges = resolve_module_dependencies(modules, files)
    assert edges == []


def test_edge_weight_counts_distinct_importing_files():
    modules = ["src/payment", "src/billing"]
    files = [
        ("src/billing/a.py", "src/billing", ["src.payment.gateway"]),
        ("src/billing/b.py", "src/billing", ["src.payment.gateway"]),
        ("src/billing/c.py", "src/billing", ["src.payment.gateway"]),
    ]
    edges = resolve_module_dependencies(modules, files)
    assert len(edges) == 1
    assert edges[0].weight == 3.0


def test_extract_external_libraries_ignores_internal_imports():
    modules = ["src/payment", "src/billing"]
    files = [
        ("src/billing/invoice.py", "src/billing", ["src.payment.gateway", "os", "requests", "requests"]),
        ("src/payment/gateway.py", "src/payment", ["numpy", "./helpers"]),
    ]
    libs = extract_external_libraries(modules, files)
    by_name = {lib.name: lib for lib in libs}
    assert set(by_name) == {"os", "requests", "numpy"}
    assert by_name["requests"].file_count == 1  # distinct importing files
    assert by_name["requests"].used_by_modules == ["src/billing"]
    assert by_name["numpy"].used_by_modules == ["src/payment"]
