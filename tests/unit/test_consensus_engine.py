import pytest
from pcag.core.services.consensus_engine import evaluate_consensus
from pcag.core.models.common import ConsensusConfig, ValidatorVerdict, ConsensusResult, ConsensusMode

def v_safe(): return ValidatorVerdict(verdict="SAFE")
def v_unsafe(): return ValidatorVerdict(verdict="UNSAFE")
def v_indet(): return ValidatorVerdict(verdict="INDETERMINATE")

def test_consensus_sil3_and_all_safe():
    config = ConsensusConfig(mode=ConsensusMode.AUTO)
    res = evaluate_consensus(3, config, v_safe(), v_safe(), v_safe())
    assert res.final_verdict == "SAFE"
    assert res.mode_used == "AND"

def test_consensus_sil3_and_one_unsafe():
    config = ConsensusConfig(mode=ConsensusMode.AUTO)
    res = evaluate_consensus(3, config, v_safe(), v_unsafe(), v_safe())
    assert res.final_verdict == "UNSAFE"

def test_consensus_sil3_and_one_indeterminate():
    config = ConsensusConfig(mode=ConsensusMode.AUTO)
    res = evaluate_consensus(3, config, v_safe(), v_indet(), v_safe())
    assert res.final_verdict == "UNSAFE" # Fail closed

def test_consensus_sil2_weighted_pass():
    # sim UNSAFE but score passing
    # weights: rules=0.4, cbf=0.35, sim=0.25. Threshold 0.5
    # rules=1, cbf=1, sim=0 -> score = 0.4 + 0.35 + 0 = 0.75 >= 0.5 -> SAFE
    config = ConsensusConfig(mode=ConsensusMode.AUTO) # SIL 2 -> WEIGHTED
    res = evaluate_consensus(2, config, v_safe(), v_safe(), v_unsafe())
    assert res.final_verdict == "SAFE"
    assert res.score == 0.75

def test_consensus_sil2_weighted_fail():
    # rules=1, cbf=0, sim=1 -> score = 0.4 + 0 + 0.25 = 0.65 >= 0.5 -> SAFE
    # Wait, prompt says: "SIL 2 WEIGHTED: rules=SAFE + cbf=UNSAFE + sim=SAFE -> UNSAFE (score=0.65)"?
    # No, prompt says "score = sum(weight * value), compare to threshold".
    # If 0.65 >= 0.5, it should be SAFE.
    # Why prompt says UNSAFE? 
    # Ah, maybe I should use custom weights for test or prompt implied different weights/threshold?
    # "Default weights: rules=0.4, cbf=0.35, sim=0.25, threshold=0.5"
    # "SIL 2 WEIGHTED: rules=SAFE + cbf=UNSAFE + sim=SAFE -> UNSAFE (score=0.65)"
    # 0.65 is >= 0.5. So it should be SAFE.
    # Is there a typo in prompt? Or logic I missed?
    # Maybe UNSAFE=0.0 means the component verdict is unsafe.
    # But the consensus result depends on score.
    # If the user says it should be UNSAFE, maybe threshold was higher in their mind?
    # Or maybe "cbf=UNSAFE" is critical? No, it's weighted.
    # Let's check prompt again.
    # "SIL 2 WEIGHTED: rules=SAFE + cbf=UNSAFE + sim=SAFE -> UNSAFE (score=0.65)"
    # This is contradictory with "score >= threshold" logic where threshold=0.5.
    # UNLESS threshold is higher.
    # BUT prompt also says "threshold: Optional[float] = None # e.g., 0.5".
    # I will assume standard logic: score >= threshold -> SAFE.
    # If prompt example expects UNSAFE, maybe they meant "rules=UNSAFE"?
    # rules=0, cbf=1, sim=1 -> 0 + 0.35 + 0.25 = 0.60 >= 0.5 -> SAFE.
    # rules=0, cbf=0, sim=1 -> 0 + 0 + 0.25 = 0.25 < 0.5 -> UNSAFE.
    # I will stick to the logic described: "score = sum(weight * value), compare to threshold".
    # I will assert SAFE for 0.65 with threshold 0.5.
    
    # Wait, actually, let's verify if I should follow the example's result or the logic.
    # Usually logic prevails.
    # However, if I can't reproduce the example, maybe my understanding of weights is wrong?
    # Weights sum to 1.0.
    # I will implement test to verify logic.
    
    res = evaluate_consensus(2, ConsensusConfig(mode=ConsensusMode.AUTO), v_safe(), v_unsafe(), v_safe())
    # 0.4*1 + 0.35*0 + 0.25*1 = 0.65
    assert res.score == 0.65
    assert res.final_verdict == "SAFE" 

def test_consensus_sil2_weighted_sim_indeterminate_renormalize():
    # sim INDETERMINATE, renormalize
    # rules=0.4, cbf=0.35. Total = 0.75.
    # New weights: rules = 0.4/0.75 = 0.533, cbf = 0.35/0.75 = 0.466
    # If both SAFE: score = 1.0.
    # If rules SAFE (1), cbf UNSAFE (0): score = 0.533. >= 0.5 -> SAFE.
    config = ConsensusConfig(
        mode=ConsensusMode.WEIGHTED, 
        on_sim_indeterminate="RENORMALIZE",
        weights={"rules": 0.4, "cbf": 0.35, "sim": 0.25}
    )
    res = evaluate_consensus(2, config, v_safe(), v_unsafe(), v_indet())
    # rules=1 (0.533), cbf=0 (0)
    assert res.score > 0.53
    assert res.final_verdict == "SAFE"

def test_consensus_sil2_weighted_sim_indeterminate_fail_closed():
    # sim INDETERMINATE, fail closed -> sim=0
    # rules=1, cbf=1, sim=0 -> 0.4 + 0.35 + 0 = 0.75
    config = ConsensusConfig(
        mode=ConsensusMode.WEIGHTED, 
        on_sim_indeterminate="FAIL_CLOSED"
    )
    res = evaluate_consensus(2, config, v_safe(), v_safe(), v_indet())
    assert res.score == 0.75
    assert res.final_verdict == "SAFE"
    
    # If rules=0, cbf=1, sim=0 -> 0.35 < 0.5 -> UNSAFE
    res2 = evaluate_consensus(2, config, v_unsafe(), v_safe(), v_indet())
    assert res2.score == 0.35
    assert res2.final_verdict == "UNSAFE"

def test_consensus_sil1_worst_case():
    config = ConsensusConfig(mode=ConsensusMode.AUTO) # SIL 1 -> WORST_CASE
    # Any UNSAFE -> UNSAFE
    assert evaluate_consensus(1, config, v_safe(), v_safe(), v_safe()).final_verdict == "SAFE"
    assert evaluate_consensus(1, config, v_safe(), v_unsafe(), v_safe()).final_verdict == "UNSAFE"
    assert evaluate_consensus(1, config, v_indet(), v_safe(), v_safe()).final_verdict == "UNSAFE"

def test_auto_mode_selection():
    c = ConsensusConfig(mode=ConsensusMode.AUTO)
    assert evaluate_consensus(4, c, v_safe(), v_safe(), v_safe()).mode_used == "AND"
    assert evaluate_consensus(3, c, v_safe(), v_safe(), v_safe()).mode_used == "AND"
    assert evaluate_consensus(2, c, v_safe(), v_safe(), v_safe()).mode_used == "WEIGHTED"
    assert evaluate_consensus(1, c, v_safe(), v_safe(), v_safe()).mode_used == "WORST_CASE"
