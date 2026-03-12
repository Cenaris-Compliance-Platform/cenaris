from app.services.policy_prompt_service import PolicyPromptService


def test_compile_prompt_file_from_text_source(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("Rule A\n\nRule B", encoding="utf-8")

    output = tmp_path / "compiled_prompt.txt"
    svc = PolicyPromptService()
    written = svc.compile_prompt_file(source_path=str(source), output_path=str(output))

    assert written == str(output)
    content = output.read_text(encoding="utf-8")
    assert "strict NDIS compliance auditor assistant" in content
    assert "Rule A" in content
    assert "Rule B" in content
