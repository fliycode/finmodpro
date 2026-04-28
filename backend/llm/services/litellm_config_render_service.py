from pathlib import Path

from llm.services.litellm_route_utils import normalize_upstream_model_name


def _extract_model_entries(snippet_text):
    lines = snippet_text.splitlines()
    if not lines:
        return []
    if lines[0].strip() != "model_list:":
        raise ValueError("Generated LiteLLM snippet must start with 'model_list:'.")
    entries = []
    for line in lines[1:]:
        if not line.strip():
            continue
        if line.lstrip().startswith("model: "):
            indent = line[: len(line) - len(line.lstrip())]
            model_name = line.split("model: ", 1)[1].strip()
            normalized_model_name = normalize_upstream_model_name(
                provider="",
                model_name=model_name,
            )
            entries.append(f"{indent}model: {normalized_model_name}")
            continue
        entries.append(line)
    return entries


def render_litellm_config(*, base_config, generated_snippets):
    generated_entries = []
    for snippet in generated_snippets:
        generated_entries.extend(_extract_model_entries(snippet))

    if not generated_entries:
        return base_config

    base_lines = base_config.splitlines()
    try:
        insert_index = next(index for index, line in enumerate(base_lines) if line.strip() == "litellm_settings:")
    except StopIteration as exc:
        raise ValueError("Base LiteLLM config is missing 'litellm_settings:'.") from exc

    rendered_lines = [
        *base_lines[:insert_index],
        *generated_entries,
        *base_lines[insert_index:],
    ]
    return "\n".join(rendered_lines) + "\n"


def build_rendered_litellm_config(*, base_config_path, generated_root, output_path):
    base_path = Path(base_config_path)
    generated_dir = Path(generated_root)
    rendered_path = Path(output_path)

    base_config = base_path.read_text(encoding="utf-8")
    generated_snippets = []
    if generated_dir.exists():
        for snippet_path in sorted(generated_dir.glob("*.yaml")):
            generated_snippets.append(snippet_path.read_text(encoding="utf-8"))

    rendered = render_litellm_config(
        base_config=base_config,
        generated_snippets=generated_snippets,
    )
    rendered_path.parent.mkdir(parents=True, exist_ok=True)
    rendered_path.write_text(rendered, encoding="utf-8")
    return {
        "output_path": str(rendered_path),
        "generated_count": len(generated_snippets),
    }


def try_build_rendered_litellm_config(*, base_config_path, generated_root, output_path):
    """Like build_rendered_litellm_config but returns None if the base config file is absent."""
    if not Path(base_config_path).exists():
        return None
    return build_rendered_litellm_config(
        base_config_path=base_config_path,
        generated_root=generated_root,
        output_path=output_path,
    )
