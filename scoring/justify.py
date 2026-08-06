"""
Turns a scored record's component notes into the actual written
justification paragraph the dashboard shows per coin — built directly
from the same notes the score components computed, so the prose can
never say something the numbers don't back up.
"""


def build_justification(coin_type: str, bucket: str, hard_filter_result: dict, score_result: dict,
                         tailwind: dict, dca: dict | None = None) -> str:
    name = "alt-coin" if coin_type == "alt" else "meme-coin"
    sentences = [f"Scored under the {name} rubric, tagged to the \"{bucket}\" narrative bucket."]

    if not hard_filter_result.get("passed", False):
        failures = "; ".join(hard_filter_result.get("failures", []))
        sentences.append(f"Disqualified by hard filters: {failures}.")
        return " ".join(sentences)

    for note in score_result.get("notes", []):
        sentences.append(note[0].upper() + note[1:] + ".")

    sentences.append(f"Base rubric score: {score_result['total']:.1f}/100.")

    if tailwind.get("tailwind_points"):
        sentences.append(f"{tailwind['note']} (+{tailwind['tailwind_points']:.1f} narrative tailwind) — final score {tailwind['final_score']:.1f}/100.")
    else:
        sentences.append(f"Final score {tailwind['final_score']:.1f}/100 ({tailwind.get('note', 'no narrative tailwind applied')}).")

    if dca is not None:
        if dca["eligible"]:
            sentences.append("Meets the DCA shortlist bar: passes hard filters, clears the survivability floor, and shows an actual upward trend in holders/volume/TVL, not just stability.")
        else:
            reasons = "; ".join(dca["reasons_failed"])
            sentences.append(f"Does not qualify for the DCA shortlist: {reasons}.")

    return " ".join(sentences)
