"""Agent Skills component (component 7) for mini-coding-agent.

A skill is a folder containing a ``skill.md`` file, for example
``skill/pr-review/skill.md``. This module:

- discovers skill folders and parses their front matter (``SkillRegistry``)
- scores prompts against skills with TF-IDF + cosine similarity (``SimilarityChecker``)
- writes a human-readable audit trail to a log file and the console (``SkillLogger``)

Standard library only. See ``spec.md`` for the full specification.
"""

import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SKILL_FILE_NAME = "skill.md"
DEFAULT_SKILL_DIR_NAMES = ("skill", "skills")
DEFAULT_THRESHOLD = 0.20
DEFAULT_LOG_PATH = Path("logs") / "skill_execution.log"
MAX_INSTRUCTION_CHARS = 6000

STOP_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "could", "do", "does", "for",
    "from", "had", "has", "have", "how", "i", "if", "in", "into", "is", "it", "its", "let", "me",
    "my", "of", "on", "or", "our", "please", "should", "so", "some", "than", "that", "the", "their",
    "them", "then", "there", "these", "this", "those", "to", "up", "us", "was", "we", "what", "when",
    "where", "which", "while", "who", "why", "will", "with", "would", "you", "your",
})


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clip(text, limit):
    text = str(text)
    return text if len(text) <= limit else text[:limit] + f"...[truncated {len(text) - limit} chars]"


def _parse_bool(value):
    return str(value).strip().lower() not in {"false", "no", "off", "0"}


#########################
#### Skill discovery ####
#########################
@dataclass
class Skill:
    name: str
    description: str
    instructions: str
    path: Path
    triggers: list = field(default_factory=list)
    enabled: bool = True

    def document(self):
        """Text used for similarity matching: name, description, and triggers (not the body)."""
        return " ".join([self.name.replace("-", " ").replace("_", " "), self.description, " ".join(self.triggers)])


def split_front_matter(text):
    """Return (metadata dict, body) for a Markdown file with an optional '---' front-matter block."""
    text = text.lstrip("﻿")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            meta = {}
            for line in lines[1:index]:
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                if ":" not in line:
                    raise ValueError(f"front matter line is not 'key: value': {line!r}")
                key, value = line.split(":", 1)
                meta[key.strip().lower()] = value.strip().strip("'\"")
            return meta, "\n".join(lines[index + 1:]).strip("\n")
    raise ValueError("front matter starts with '---' but is never closed")


def first_paragraph(body):
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if block and not block.startswith("#"):
            return " ".join(block.split())
    return ""


def parse_skill_file(path):
    path = Path(path)
    meta, body = split_front_matter(path.read_text(encoding="utf-8"))
    triggers = [item.strip() for item in meta.get("triggers", "").split(",") if item.strip()]
    return Skill(
        name=meta.get("name") or path.parent.name,
        description=meta.get("description") or first_paragraph(body),
        instructions=body.strip(),
        path=path.resolve(),
        triggers=triggers,
        enabled=_parse_bool(meta.get("enabled", "true")),
    )


def default_skill_roots(workspace_root, extra_dirs=()):
    """Spec 1.1: workspace skill/ and skills/, the agent's bundled skill/, then CLI extras."""
    workspace_root = Path(workspace_root)
    roots = [workspace_root / name for name in DEFAULT_SKILL_DIR_NAMES]
    roots.append(Path(__file__).resolve().parent / "skill")
    roots.extend(Path(item) for item in extra_dirs)
    return roots


class SkillRegistry:
    def __init__(self, roots):
        self.roots = [Path(root) for root in roots]
        self.skills = {}
        self.errors = []      # (path, message)
        self.duplicates = []  # (name, path)

    def discover(self):
        self.skills, self.errors, self.duplicates = {}, [], []
        seen_dirs = set()
        for root in self.roots:
            if not root.is_dir():
                continue
            for folder in sorted(root.iterdir(), key=lambda item: item.name.lower()):
                if not folder.is_dir() or folder.name.startswith(("_", ".")):
                    continue
                resolved = folder.resolve()
                if resolved in seen_dirs:
                    continue
                seen_dirs.add(resolved)
                skill_file = next(
                    (item for item in folder.iterdir() if item.is_file() and item.name.lower() == SKILL_FILE_NAME),
                    None,
                )
                if skill_file is None:
                    continue
                try:
                    skill = parse_skill_file(skill_file)
                except (OSError, ValueError) as exc:
                    self.errors.append((skill_file, str(exc)))
                    continue
                if skill.name in self.skills:
                    self.duplicates.append((skill.name, skill.path))
                    continue
                self.skills[skill.name] = skill
        return self

    def all(self):
        return list(self.skills.values())

    def enabled(self):
        return [skill for skill in self.skills.values() if skill.enabled]

    def get(self, name):
        return self.skills.get(name)


###############################
#### Similarity & matching ####
###############################
def stem(word):
    if word.endswith("ies") and len(word) > 4:
        word = word[:-3] + "y"
    elif word.endswith("ing") and len(word) > 5:
        word = word[:-3]
    elif word.endswith("ed") and len(word) > 4:
        word = word[:-2]
    elif word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        word = word[:-1]
    if word.endswith("e") and len(word) > 4:
        word = word[:-1]
    return word


def tokenize(text):
    words = re.findall(r"[a-z0-9]+", str(text).lower())
    return [stem(word) for word in words if len(word) > 1 and word not in STOP_WORDS]


def normalize_phrase(text):
    return " ".join(re.findall(r"[a-z0-9]+", str(text).lower()))


@dataclass
class SkillMatch:
    skill: Skill
    score: float
    method: str
    triggered: bool = False


class SimilarityChecker:
    """TF-IDF + cosine similarity between a query and each enabled skill's document (spec section 2)."""

    method = "tfidf-cosine"

    def __init__(self, registry, threshold=DEFAULT_THRESHOLD):
        self.registry = registry
        self.threshold = float(threshold)
        self._fit()

    def _fit(self):
        self.skills = sorted(self.registry.enabled(), key=lambda skill: skill.name)
        self.n_docs = len(self.skills)
        doc_tokens = [Counter(tokenize(skill.document())) for skill in self.skills]
        df = Counter(term for tokens in doc_tokens for term in tokens)
        self.idf = {term: math.log((1 + self.n_docs) / (1 + count)) + 1 for term, count in df.items()}
        self.unknown_idf = math.log(1 + self.n_docs) + 1
        self.vectors = [self._weights(tokens) for tokens in doc_tokens]

    def _weights(self, counts):
        return {term: count * self.idf.get(term, self.unknown_idf) for term, count in counts.items()}

    @staticmethod
    def _cosine(left, right):
        dot = sum(weight * right.get(term, 0.0) for term, weight in left.items())
        norm = math.sqrt(sum(w * w for w in left.values())) * math.sqrt(sum(w * w for w in right.values()))
        return dot / norm if norm else 0.0

    def score(self, query):
        """Return every enabled skill ranked by score (highest first); the best one is marked if it passes."""
        query_vector = self._weights(Counter(tokenize(query)))
        phrase = f" {normalize_phrase(query)} "
        matches = []
        for skill, vector in zip(self.skills, self.vectors):
            if f" {normalize_phrase(skill.name)} " in phrase:
                matches.append(SkillMatch(skill, 1.0, "name-match"))
            else:
                matches.append(SkillMatch(skill, self._cosine(query_vector, vector), self.method))
        matches.sort(key=lambda match: (-match.score, match.skill.name))
        if matches and matches[0].score >= self.threshold:
            matches[0].triggered = True
        return matches

    @staticmethod
    def best(matches):
        return matches[0] if matches and matches[0].triggered else None


#################
#### Logging ####
#################
class SkillLogger:
    """Human-readable audit trail written to a log file and (optionally) the console (spec section 4)."""

    def __init__(self, path=DEFAULT_LOG_PATH, console=True, base_dir=None, session_id="-", stream=None):
        self.path = Path(path)
        self.console = console
        self.base_dir = Path(base_dir).resolve() if base_dir else None
        self.session_id = session_id
        self.stream = stream

    def display_path(self, path):
        path = Path(path)
        if self.base_dir:
            try:
                return path.resolve().relative_to(self.base_dir).as_posix()
            except ValueError:
                pass
        return str(path)

    def write(self, event, fields="", details=()):
        header = f"{_now()} | session={self.session_id} | {event}"
        if fields:
            header += f" | {fields}"
        text = "\n".join([header, *(f"    {line}" for line in details)]) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(text)
        if self.console:
            stream = self.stream or sys.stderr
            stream.write("[skills] " + text.replace("\n    ", "\n[skills]     "))
            stream.flush()

    def discovery(self, registry):
        rows = [
            f"{skill.name:<16} [{'enabled' if skill.enabled else 'disabled':<8}]  {self.display_path(skill.path)}"
            for skill in registry.all()
        ]
        self.write(
            "SKILL_DISCOVERY",
            f"roots={len(registry.roots)} found={len(registry.all())} enabled={len(registry.enabled())}",
            rows or ["(no skills found)"],
        )
        for path, message in registry.errors:
            self.write("SKILL_LOAD_ERROR", f"path={self.display_path(path)}", [message])
        for name, path in registry.duplicates:
            self.write("SKILL_DUPLICATE_SKIPPED", f"name={name} path={self.display_path(path)}")

    def prompt_received(self, prompt, source):
        self.write("PROMPT_RECEIVED", f"source={source}", [f'prompt: "{_clip(" ".join(str(prompt).split()), 500)}"'])

    def similarity_check(self, matches, threshold, method):
        rows = []
        for rank, match in enumerate(matches, start=1):
            status = "MATCH" if match.triggered else "below-threshold"
            rows.append(
                f"{rank}. {match.skill.name:<16} score={match.score:.4f}  {match.method:<12}  "
                f"{status:<15}  {self.display_path(match.skill.path)}"
            )
        self.write(
            "SIMILARITY_CHECK",
            f"method={method} threshold={threshold:.2f} candidates={len(matches)}",
            rows or ["(no enabled skills)"],
        )

    def skill_triggered(self, match, source, injected_chars):
        self.write(
            "SKILL_TRIGGERED",
            f"skill={match.skill.name} score={match.score:.4f} source={source} path={self.display_path(match.skill.path)}",
            [f"injected {injected_chars} chars of instructions into the prompt"],
        )

    def no_skill_triggered(self, matches, threshold):
        best = matches[0] if matches else None
        self.write(
            "NO_SKILL_TRIGGERED",
            f"best={best.skill.name if best else 'none'} best_score={best.score if best else 0.0:.4f} "
            f"threshold={threshold:.2f}",
        )

    def execution_complete(self, skill, steps, final):
        self.write(
            "SKILL_EXECUTION_COMPLETE",
            f"skill={skill.name} steps={steps}",
            [f'final: "{_clip(" ".join(str(final).split()), 300)}"'],
        )
