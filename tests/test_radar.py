"""Tests for the radar's deterministic pieces (no network)."""

from paperscout.models import Author, Paper
from paperscout.radar.pillars import Pillar, load_pillars
from paperscout.radar.score import score_papers
from paperscout.sources import paperfile
from paperscout.sources.openalex import reconstruct_abstract


def test_reconstruct_abstract():
    inv = {"Causal": [0], "inference": [1], "over": [2], "time": [3]}
    assert reconstruct_abstract(inv) == "Causal inference over time"
    assert reconstruct_abstract(None) == ""


def test_paperfile_author_parsing(tmp_path):
    p = tmp_path / "papers.csv"
    p.write_text(
        "title,abstract,authors\n"
        "A Causal Method,Estimating treatment effects over time,"
        "Jane Doe (MIT); John Roe (Stanford)\n",
        encoding="utf-8",
    )
    papers = paperfile.load(p)
    assert len(papers) == 1
    a = papers[0].authors
    assert a[0].name == "Jane Doe" and a[0].affiliation == "MIT"
    assert a[1].name == "John Roe" and a[1].affiliation == "Stanford"


def test_scoring_ranks_relevant_above_irrelevant():
    causal = Paper(
        title="Conditional average treatment effect estimation under confounding",
        abstract=("We estimate treatment effects with time-varying confounding using a "
                  "causal inference framework, instrumental variables and sensitivity analysis."),
    )
    graph = Paper(
        title="A graph neural network for link prediction on knowledge graphs",
        abstract=("Message passing and graph attention for link prediction and node "
                  "embedding on relational knowledge graphs."),
    )
    irrelevant = Paper(
        title="A new sorting algorithm for embedded systems",
        abstract="We present a cache-friendly sorting routine for microcontrollers.",
    )
    scored = score_papers([causal, graph, irrelevant])
    keys = {sp.paper.title: sp for sp in scored}
    # the irrelevant CS paper should not match any default pillar
    assert "A new sorting algorithm for embedded systems" not in keys
    assert keys[causal.title].pillars[0] == "CAUSAL"
    assert "GRAPH" in keys[graph.title].pillars


def test_custom_pillars_loaded_from_json(tmp_path):
    cfg = tmp_path / "pillars.local.json"
    cfg.write_text(
        '[{"key":"ROBOTICS","name":"Robotics","profile":"robot manipulation grasping '
        'reinforcement learning control","terms":["robot","manipulation","grasping"],'
        '"core":true}]',
        encoding="utf-8",
    )
    pillars = load_pillars(cfg)
    assert len(pillars) == 1 and pillars[0].key == "ROBOTICS"
    paper = Paper(title="Robot manipulation via grasping",
                  abstract="A robot learns manipulation and grasping with reinforcement learning.")
    scored = score_papers([paper], pillars)
    assert scored and scored[0].pillars == ["ROBOTICS"]


def test_default_pillars_when_none():
    assert load_pillars(None)  # ships a usable default set
