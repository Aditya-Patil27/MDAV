from datetime import datetime


class FusionService:
    WEIGHTS = {
        "visual": 0.40,
        "semantic": 0.35,
        "signature": 0.25,
    }

    THRESHOLDS = {
        "approved": 0.8,
        "flagged": 0.5,
    }

    def fuse(self, vision_result: dict, semantic_result: dict, signature_result: dict) -> dict:
        visual_score = self._compute_visual_score(vision_result)
        semantic_score = self._compute_semantic_score(semantic_result)
        signature_score = self._compute_signature_score(signature_result)

        has_signature = signature_result.get("signature_detected", False)

        if not has_signature:
            final_score = 0.60 * visual_score + 0.40 * semantic_score
        else:
            final_score = (
                self.WEIGHTS["visual"] * visual_score
                + self.WEIGHTS["semantic"] * semantic_score
                + self.WEIGHTS["signature"] * signature_score
            )

        final_score = max(0.0, min(1.0, final_score))
        decision = self._determine_decision(final_score)
        reason = self._generate_reason(
            visual_score, semantic_score, signature_score, decision, has_signature
        )

        return {
            "visual_score": round(visual_score, 4),
            "semantic_score": round(semantic_score, 4),
            "signature_score": round(signature_score, 4),
            "final_score": round(final_score, 4),
            "decision": decision,
            "reason_summary": reason,
        }

    def _compute_visual_score(self, vision_result: dict) -> float:
        if not vision_result:
            return 0.5

        tamper_prob = vision_result.get("tamper_probability", 0.5)
        return 1.0 - tamper_prob

    def _compute_semantic_score(self, semantic_result: dict) -> float:
        if not semantic_result:
            return 0.5

        consistency_score = semantic_result.get("consistency_score", 0.5)
        return consistency_score

    def _compute_signature_score(self, signature_result: dict) -> float:
        if not signature_result:
            return 0.5

        if not signature_result.get("signature_detected", False):
            return 0.5

        if signature_result.get("validation_result") == "VALID":
            return 1.0
        elif signature_result.get("validation_result") == "INVALID":
            return 0.0
        else:
            return 0.5

    def _determine_decision(self, score: float) -> str:
        if score >= self.THRESHOLDS["approved"]:
            return "APPROVED"
        elif score >= self.THRESHOLDS["flagged"]:
            return "FLAGGED"
        else:
            return "REVIEW_REQUIRED"

    def _generate_reason(
        self,
        visual_score: float,
        semantic_score: float,
        signature_score: float,
        decision: str,
        has_signature: bool,
    ) -> str:
        reasons = []

        if visual_score >= 0.7:
            reasons.append("Visual analysis shows no significant tampering")
        elif visual_score >= 0.4:
            reasons.append("Visual analysis detected minor anomalies")
        else:
            reasons.append("Visual analysis detected significant tampering indicators")

        if semantic_score >= 0.7:
            reasons.append("Document fields are consistent and valid")
        elif semantic_score >= 0.4:
            reasons.append("Some document fields could not be validated")
        else:
            reasons.append("Document fields show inconsistencies or are missing")

        if has_signature:
            if signature_score >= 0.7:
                reasons.append("Digital signature is valid and intact")
            elif signature_score >= 0.4:
                reasons.append("Digital signature validation incomplete")
            else:
                reasons.append("Digital signature is invalid or missing")
        else:
            reasons.append("No digital signature detected in document")

        return ". ".join(reasons) + f". Overall assessment: {decision}."


fusion_service = FusionService()
