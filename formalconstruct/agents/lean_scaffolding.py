from __future__ import annotations

from formalconstruct.core.exceptions import ScaffoldingError
from formalconstruct.domains.registry import DomainRegistry
from formalconstruct.prompts.loader import render_lean_scaffold
from formalconstruct.schemas.lean_source import (
    LeanDeclaration,
    LeanGoal,
    LeanSource,
    SourceMappingEntry,
    parse_declarations,
)
from formalconstruct.schemas.problem_spec import (
    BaseType,
    IndexType,
    ObjectiveDirection,
    ProblemSpec,
    SequenceRelationType,
)


# Type alias for attributed line metadata:
# (line_index_in_block, schema_field, narrative_start, narrative_end)
_AttrEntry = tuple[int, str, int, int]


class LeanScaffoldingAgent:
    """Deterministic rule engine.

    Consumes a validated ProblemSpec and produces a Lean 4 source file
    with sorry macros at each proof obligation.  No LLM calls -- this
    agent delegates all domain-specific mapping to the DomainRegistry."""

    def __init__(self, registry: DomainRegistry) -> None:
        self._registry = registry

    def scaffold(
        self, problem_spec: ProblemSpec, narrative: str = ""
    ) -> LeanSource:
        """Consume ProblemSpec, produce Lean 4 source with sorry macros."""
        domain_key = (
            problem_spec.primary_domain.value
            if problem_spec.domain_components and problem_spec.primary_domain
            else problem_spec.problem_domain.value
        )
        mapper = self._registry.get_mapper(
            domain_key,
            (
                [d.value for d in problem_spec.domain_components]
                if problem_spec.domain_components
                else None
            ),
        )

        if hasattr(mapper, 'set_context'):
            mapper.set_context(problem_spec)

        try:
            try:
                imports = mapper.required_imports(problem_spec)
            except Exception as exc:
                raise ScaffoldingError(f"Failed to collect imports: {exc}") from exc

            narrative_lower = narrative.lower()
            _last_narrative_pos = 0

            def _find_narrative_span(hint: str) -> tuple[int, int]:
                nonlocal _last_narrative_pos
                idx = narrative_lower.find(hint.lower(), _last_narrative_pos)
                if idx < 0:
                    idx = narrative_lower.find(hint.lower())
                if idx >= 0:
                    _last_narrative_pos = idx + len(hint)
                    return (idx, idx + len(hint))
                return (-1, -1)

            # ── Import block ──────────────────────────────────────
            import_lines = []
            for imp in imports:
                if not imp.startswith("import "):
                    imp = f"import {imp}"
                import_lines.append(imp)
            import_block = "\n".join(import_lines)

            # `∑`/`∏` notation requires the BigOperators scope to be open.
            needs_bigops = (
                problem_spec.objective.summation is not None
                or any(
                    sr.type in (
                        SequenceRelationType.SUM_CONSTRAINT,
                        SequenceRelationType.PRODUCT_CONSTRAINT,
                    )
                    for sr in problem_spec.sequence_relations
                )
            )
            extra_import_lines = 0
            if needs_bigops:
                import_block = import_block + "\nopen scoped BigOperators"
                extra_import_lines = 1

            # ── Dimension variable ────────────────────────────────
            needs_dim_var = any(
                s.base_type == BaseType.REAL_N and s.dimension is None
                for s in problem_spec.spaces
            )

            # ── Space definitions ─────────────────────────────────
            spaces_dict = {s.name: s for s in problem_spec.spaces}
            space_lines: list[str] = []
            space_attrs: list[_AttrEntry] = []
            for i, space in enumerate(problem_spec.spaces):
                space_def = mapper.map_space(space)
                if space_def:
                    start, end = _find_narrative_span(space.name)
                    for sub in space_def.split("\n"):
                        space_attrs.append(
                            (len(space_lines), f"spaces[{i}]", start, end)
                        )
                        space_lines.append(sub)
            space_block = "\n".join(space_lines) if space_lines else None

            # ── Variable declarations ─────────────────────────────
            variable_lines: list[str] = []
            variable_attrs: list[_AttrEntry] = []
            for i, var in enumerate(problem_spec.variables):
                var_decl = mapper.map_variable(var, spaces_dict)
                if var_decl:
                    start, end = _find_narrative_span(var.symbol)
                    for sub in var_decl.split("\n"):
                        variable_attrs.append(
                            (len(variable_lines), f"variables[{i}]", start, end)
                        )
                        variable_lines.append(sub)

            def _append_decl(text: str, schema_field: str, hint: str = "") -> None:
                if not text:
                    return
                start, end = _find_narrative_span(hint) if hint else (-1, -1)
                for sub in text.split("\n"):
                    variable_attrs.append((len(variable_lines), schema_field, start, end))
                    variable_lines.append(sub)

            # ── Dimension variable(s) for indexed/summation constructs ──
            if not needs_dim_var:
                dim_names: list[str] = []
                for iv in problem_spec.indexed_variables:
                    if iv.index_type == IndexType.FIN_N and "n" not in dim_names:
                        dim_names.append("n")
                for sr in problem_spec.sequence_relations:
                    if sr.type in (
                        SequenceRelationType.SUM_CONSTRAINT,
                        SequenceRelationType.PRODUCT_CONSTRAINT,
                    ) and not sr.index_upper.isdigit() and sr.index_upper not in dim_names:
                        dim_names.append(sr.index_upper)
                summ = problem_spec.objective.summation
                if summ is not None and not summ.index_upper.isdigit() and summ.index_upper not in dim_names:
                    dim_names.append(summ.index_upper)
                for name in dim_names:
                    _append_decl(f"variable ({name} : ℕ)", "indexed_variables")

            # ── Indexed/sequence variable declarations ──
            for i, iv in enumerate(problem_spec.indexed_variables):
                _append_decl(
                    mapper.map_indexed_variable(iv), f"indexed_variables[{i}]", iv.symbol
                )

            variable_block = "\n".join(variable_lines) if variable_lines else None

            # ── Relation hypotheses (constraints + sequence relations) ──
            # Collected separately and rendered just before the theorem (after
            # the function block) so they may reference declared functions
            # without producing a use-before-declaration in the Lean output.
            relation_hyp_lines: list[str] = []
            relation_hyp_attrs: list[tuple[str, int, int]] = []
            for i, c in enumerate(problem_spec.constraints):
                hyp = mapper.map_constraint(c, i)
                if hyp:
                    start, end = _find_narrative_span(c.description or c.expression)
                    for sub in hyp.split("\n"):
                        relation_hyp_lines.append(sub)
                        relation_hyp_attrs.append((f"constraints[{i}]", start, end))
            for i, sr in enumerate(problem_spec.sequence_relations):
                hyp = mapper.map_sequence_relation(sr, i)
                if hyp:
                    start, end = _find_narrative_span(sr.left)
                    for sub in hyp.split("\n"):
                        relation_hyp_lines.append(sub)
                        relation_hyp_attrs.append((f"sequence_relations[{i}]", start, end))

            # ── Objective → preamble + theorem ────────────────────
            theorem_str = mapper.map_objective(
                problem_spec.objective, problem_spec
            )
            preamble_lines: list[str] = []
            preamble_attrs: list[_AttrEntry] = []
            theorem_block_lines: list[str] = []
            theorem_block_attrs: list[_AttrEntry] = []

            if theorem_str:
                obj_lines = theorem_str.split("\n")
                raw_preamble: list[str] = []
                raw_theorem: list[str] = []
                in_theorem = False
                for ol in obj_lines:
                    stripped = ol.lstrip()
                    if stripped.startswith("theorem "):
                        in_theorem = True
                    if in_theorem:
                        raw_theorem.append(ol)
                    else:
                        raw_preamble.append(ol)

                # Process preamble lines with attribution
                if raw_preamble:
                    for p_line in raw_preamble:
                        stripped = p_line.strip()
                        if not stripped:
                            preamble_lines.append("")
                            continue

                        if stripped.startswith("def "):
                            def_name = (
                                stripped.split()[1]
                                if len(stripped.split()) > 1
                                else ""
                            )
                            schema_field = "objective.preamble"
                            for si, sp in enumerate(problem_spec.spaces):
                                if sp.name == def_name:
                                    schema_field = f"spaces[{si}]"
                                    break
                            start, end = _find_narrative_span(def_name)
                            for sub in p_line.split("\n"):
                                preamble_attrs.append(
                                    (len(preamble_lines), schema_field, start, end)
                                )
                                preamble_lines.append(sub)

                        elif stripped.startswith("lemma "):
                            schema_field = "objective.preamble"
                            for vi, var in enumerate(problem_spec.variables):
                                if var.bounds and (
                                    var.bounds.lower_bound is not None
                                    or var.bounds.upper_bound is not None
                                ):
                                    schema_field = f"variables[{vi}].bounds"
                                    break
                            start, end = _find_narrative_span("convex")
                            for sub in p_line.split("\n"):
                                preamble_attrs.append(
                                    (len(preamble_lines), schema_field, start, end)
                                )
                                preamble_lines.append(sub)

                        else:
                            preamble_attrs.append(
                                (len(preamble_lines), "objective.preamble", -1, -1)
                            )
                            preamble_lines.append(p_line)

                # Process theorem block
                if raw_theorem:
                    start, end = _find_narrative_span(
                        problem_spec.objective.expression_latex
                    )
                    for sub in "\n".join(raw_theorem).split("\n"):
                        theorem_block_attrs.append(
                            (len(theorem_block_lines), "objective", start, end)
                        )
                        theorem_block_lines.append(sub)

            # Strip trailing blank lines -- the template's double-blank
            # after the preamble section provides the correct spacing.
            while preamble_lines and preamble_lines[-1] == "":
                preamble_lines.pop()
            preamble_block = (
                "\n".join(preamble_lines) if preamble_lines else None
            )
            theorem_block_str = (
                "\n".join(theorem_block_lines) if theorem_block_lines else None
            )

            # ── Function hypotheses (LeanDeclaration dedup) ───────
            all_func_decls: list[tuple[LeanDeclaration, int]] = []
            for i, func in enumerate(problem_spec.functions):
                func_hyp = mapper.map_function(func)
                if func_hyp:
                    decls = parse_declarations(
                        func_hyp, schema_field=f"functions[{i}]"
                    )
                    for decl in decls:
                        all_func_decls.append((decl, i))

            seen: set[tuple[str, str]] = set()
            function_lines: list[str] = []
            function_attrs: list[_AttrEntry] = []
            for decl, func_idx in all_func_decls:
                key = (decl.kind, decl.name)
                if key not in seen:
                    seen.add(key)
                    start, end = _find_narrative_span(
                        problem_spec.functions[func_idx].symbol
                    )
                    for sub in decl.content.split("\n"):
                        function_attrs.append(
                            (len(function_lines), decl.schema_field, start, end)
                        )
                        function_lines.append(sub)
            function_block = (
                "\n".join(function_lines) if function_lines else None
            )

            # ── Relation hypotheses + `include`, prepended to the theorem ──
            # Relation hypotheses render here (after the function block) so they
            # can reference declared functions. Section `variable` hypotheses are
            # only auto-bound into a theorem when referenced in its statement;
            # inequality/existential goals reference data variables but not their
            # hypotheses, so a Lean `include` binds them explicitly.
            prefix: list[str] = list(relation_hyp_lines)
            prefix_attrs: list[tuple[str, int, int]] = list(relation_hyp_attrs)
            if problem_spec.objective.direction in (
                ObjectiveDirection.INEQUALITY,
                ObjectiveDirection.EXISTENTIAL_BOUND,
            ):
                hyp_names = _collect_hypothesis_names(variable_lines)
                hyp_names += _collect_hypothesis_names(relation_hyp_lines)
                hyp_names += _collect_hypothesis_names(function_lines)
                if hyp_names:
                    prefix.append("include " + " ".join(hyp_names))
                    prefix_attrs.append(("objective.hypotheses", -1, -1))
            if prefix and theorem_block_lines:
                n = len(prefix)
                theorem_block_attrs = (
                    [(i, sf, ns, ne) for i, (sf, ns, ne) in enumerate(prefix_attrs)]
                    + [(idx + n, sf, ns, ne) for (idx, sf, ns, ne) in theorem_block_attrs]
                )
                theorem_block_lines = prefix + theorem_block_lines
                theorem_block_str = "\n".join(theorem_block_lines)

            # ── Render via Jinja2 template ────────────────────────
            content = render_lean_scaffold(
                import_block=import_block,
                dimension_variable=needs_dim_var,
                space_block=space_block,
                variable_block=variable_block,
                preamble_block=preamble_block,
                function_block=function_block,
                theorem_block=theorem_block_str,
            )

            # ── Build source mappings via line counting ───────────
            mappings: list[SourceMappingEntry] = []
            line_offset = len(import_lines) + extra_import_lines  # import lines
            line_offset += 1  # blank after imports

            if needs_dim_var:
                line_offset += 2  # "variable (n : N)" + blank

            if space_block is not None:
                for idx, sf, ns, ne in space_attrs:
                    mappings.append(SourceMappingEntry(
                        lean_line=line_offset + idx + 1,
                        schema_field=sf,
                        narrative_start=ns,
                        narrative_end=ne,
                    ))
                line_offset += len(space_lines)
                line_offset += 1  # blank

            if variable_block is not None:
                for idx, sf, ns, ne in variable_attrs:
                    mappings.append(SourceMappingEntry(
                        lean_line=line_offset + idx + 1,
                        schema_field=sf,
                        narrative_start=ns,
                        narrative_end=ne,
                    ))
                line_offset += len(variable_lines)
                line_offset += 1  # blank

            if preamble_block is not None:
                for idx, sf, ns, ne in preamble_attrs:
                    mappings.append(SourceMappingEntry(
                        lean_line=line_offset + idx + 1,
                        schema_field=sf,
                        narrative_start=ns,
                        narrative_end=ne,
                    ))
                line_offset += len(preamble_lines)
                line_offset += 2  # double blank after preamble

            if function_block is not None:
                for idx, sf, ns, ne in function_attrs:
                    mappings.append(SourceMappingEntry(
                        lean_line=line_offset + idx + 1,
                        schema_field=sf,
                        narrative_start=ns,
                        narrative_end=ne,
                    ))
                line_offset += len(function_lines)
                line_offset += 1  # blank

            if theorem_block_str is not None:
                for idx, sf, ns, ne in theorem_block_attrs:
                    mappings.append(SourceMappingEntry(
                        lean_line=line_offset + idx + 1,
                        schema_field=sf,
                        narrative_start=ns,
                        narrative_end=ne,
                    ))

            # ── Parse sorry locations ─────────────────────────────
            goals: list[LeanGoal] = []
            for i, line in enumerate(content.split("\n"), start=1):
                sorry_idx = line.find("sorry")
                if sorry_idx >= 0:
                    theorem_name = _find_theorem_name(content, i)
                    goals.append(
                        LeanGoal(
                            goal_id=f"goal_{len(goals)}",
                            theorem_name=theorem_name,
                            goal_state="",
                            line_number=i,
                            sorry_offset=sorry_idx,
                        )
                    )
        finally:
            if hasattr(mapper, 'clear_context'):
                mapper.clear_context()

        return LeanSource(
            content=content,
            imports=[imp.replace("import ", "") for imp in imports],
            goals=goals,
            mathlib_modules=[
                imp.replace("import ", "") for imp in imports if "Mathlib" in imp
            ],
            source_mappings=mappings,
        )


def _collect_hypothesis_names(lines: list[str]) -> list[str]:
    """Return hypothesis variable names (``variable (h... : ...)``) in order.

    Used to emit a Lean ``include`` so section-variable hypotheses are bound
    into a theorem whose statement does not itself reference them."""
    names: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("variable (h"):
            inner = stripped[len("variable ("):]
            name = inner.split(":")[0].split()[0].strip().rstrip(")")
            if name and name not in names:
                names.append(name)
    return names


def _find_theorem_name(content: str, sorry_line: int) -> str:
    """Search backwards from sorry line to find the theorem/lemma name."""
    lines = content.split("\n")
    for i in range(sorry_line - 1, -1, -1):
        line = lines[i] if i < len(lines) else ""
        stripped = line.lstrip()
        for keyword in ("theorem ", "lemma ", "def "):
            if stripped.startswith(keyword):
                rest = stripped.split(keyword, 1)[1].strip()
                name = rest.split()[0].split("(")[0].rstrip(":") if rest.split() else "unknown"
                return name
    return "unknown"
