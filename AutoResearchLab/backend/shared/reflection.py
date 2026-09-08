"""
Agent 自迭代框架：self-evaluate → learn (生成 skill) → re-execute。
三个 Agent (idea/plan/task) 共用此模块，仅 prompt 和评估维度不同。
"""

import asyncio
from typing import Any, Callable, Optional

from loguru import logger

from shared.constants import (
    REFLECT_MAX_ITERATIONS,
    REFLECT_QUALITY_THRESHOLD,
)
from shared.reflection_helpers import (
    _raise_if_aborted,
    generate_skill_from_reflection,
    save_learned_skill,
    self_evaluate,
)


async def reflection_loop(
    agent_type: str,
    run_fn: Callable,
    initial_output: Any,
    context: dict,
    on_thinking: Optional[Callable] = None,
    abort_event: Optional[Any] = None,
    api_config: Optional[dict] = None,
) -> dict:
    """
    完整的自迭代循环：evaluate → learn → re-execute → evaluate ...
    返回 {output, reflection} 其中 reflection 包含评估结果和 skill 信息。

    参数:
        agent_type: "idea" | "plan" | "task"
        run_fn: 重新执行的 async callable，签名由各 agent 适配
        initial_output: Agent 首次执行的输出
        context: 评估上下文（idea、task_id 等）
        on_thinking: thinking 回调
        abort_event: 中止事件
        api_config: 含 reflectionEnabled/reflectionMaxIterations/reflectionQualityThreshold
    """
    cfg = api_config or {}
    enabled = cfg.get("reflectionEnabled", False)
    max_iterations = cfg.get("reflectionMaxIterations", REFLECT_MAX_ITERATIONS)
    threshold = cfg.get("reflectionQualityThreshold", REFLECT_QUALITY_THRESHOLD)

    if not enabled:
        return {"output": initial_output, "reflection": None}

    use_mock = cfg.get(f"{agent_type}UseMock", False)
    if use_mock:
        return {"output": initial_output, "reflection": None}

    best_output = initial_output
    best_score = 0
    skills_created = []
    all_evaluations = []

    current_output = initial_output
    for iteration in range(max_iterations + 1):
        _raise_if_aborted(abort_event)

        if on_thinking:
            separator = f"\n\n---\n**Self-Reflection (iteration {iteration + 1}/{max_iterations + 1})**\n\n"
            r = on_thinking(separator, task_id=None, operation="Reflect", schedule_info={
                "turn": iteration + 1,
                "max_turns": max_iterations + 1,
                "operation": "Reflect",
            })
            if asyncio.iscoroutine(r):
                await r

        try:
            evaluation = await self_evaluate(
                agent_type, current_output, context,
                on_thinking=on_thinking, abort_event=abort_event, api_config=api_config,
            )
        except Exception as e:
            logger.warning("Self-evaluation failed for %s (iteration %d): %s", agent_type, iteration, e)
            break

        all_evaluations.append(evaluation)
        score = evaluation.get("score", 0)

        if score > best_score:
            best_score = score
            best_output = current_output

        if score >= threshold:
            logger.info("%s reflection: score %d >= threshold %d, accepting output", agent_type, score, threshold)
            suggestion = evaluation.get("skill_suggestion", {})
            if suggestion.get("should_create") and suggestion.get("name"):
                try:
                    skill_content = await generate_skill_from_reflection(
                        agent_type, evaluation, context,
                        api_config=api_config, abort_event=abort_event,
                    )
                    if skill_content:
                        path = save_learned_skill(agent_type, suggestion["name"], skill_content)
                        skills_created.append({"name": suggestion["name"], "path": str(path)})
                except Exception as e:
                    logger.warning("Skill generation failed: %s", e)
            break

        if iteration >= max_iterations:
            logger.info("%s reflection: max iterations reached, returning best (score=%d)", agent_type, best_score)
            break

        suggestion = evaluation.get("skill_suggestion", {})
        if suggestion.get("should_create") and suggestion.get("name"):
            try:
                _raise_if_aborted(abort_event)
                skill_content = await generate_skill_from_reflection(
                    agent_type, evaluation, context,
                    api_config=api_config, abort_event=abort_event,
                )
                if skill_content:
                    path = save_learned_skill(agent_type, suggestion["name"], skill_content)
                    skills_created.append({"name": suggestion["name"], "path": str(path)})
                    if on_thinking:
                        msg = f"\n\n> Learned skill: **{suggestion['name']}** saved for future use.\n\n"
                        r = on_thinking(msg, task_id=None, operation="Reflect", schedule_info=None)
                        if asyncio.iscoroutine(r):
                            await r
            except Exception as e:
                logger.warning("Skill generation failed: %s", e)

        if on_thinking:
            msg = f"\n\n> Score {score} < threshold {threshold}. Re-executing with improved context...\n\n"
            r = on_thinking(msg, task_id=None, operation="Reflect", schedule_info=None)
            if asyncio.iscoroutine(r):
                await r

        try:
            _raise_if_aborted(abort_event)
            current_output = await run_fn()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Re-execution failed for %s: %s", agent_type, e)
            break

    return {
        "output": best_output,
        "reflection": {
            "iterations": len(all_evaluations),
            "best_score": best_score,
            "evaluations": all_evaluations,
            "skills_created": skills_created,
        },
    }
