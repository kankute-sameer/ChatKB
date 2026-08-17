from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from app.core.deps import get_current_user
from app.core.ids import new_id
from app.core.tracing import get_tracer

router = APIRouter(tags=["feedback"])


class ExperienceFeedbackRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=2000)

    @field_validator("comment")
    @classmethod
    def comment_must_have_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Feedback cannot be empty")
        return normalized


class ExperienceFeedbackResponse(BaseModel):
    submitted: bool = True


class ProductOpenedResponse(BaseModel):
    logged: bool = True


@router.post("/v1/product/opened", response_model=ProductOpenedResponse)
async def log_product_opened(
    owner_id: Annotated[str, Depends(get_current_user)],
) -> ProductOpenedResponse:
    event_id = new_id("event")
    tracer = get_tracer()
    metadata = {
        "event_id": event_id,
        "user_id": owner_id,
        "user_name": owner_id,
        "source": "login",
    }
    with tracer.trace(
        "product.opened",
        input={"source": "login"},
        user_id=owner_id,
        trace_id_seed=event_id,
        metadata=metadata,
    ) as observation:
        observation.update(output={"opened": True})
    tracer.score_trace(
        event_id,
        name="product-opened",
        value=True,
        data_type="BOOLEAN",
        score_id_seed=f"product-opened:{event_id}",
        metadata=metadata,
    )
    tracer.schedule_flush()
    return ProductOpenedResponse()


@router.post("/v1/feedback", response_model=ExperienceFeedbackResponse)
async def submit_feedback(
    body: ExperienceFeedbackRequest,
    owner_id: Annotated[str, Depends(get_current_user)],
) -> ExperienceFeedbackResponse:
    comment = body.comment
    feedback_id = new_id("feedback")
    tracer = get_tracer()
    with tracer.trace(
        "product.feedback",
        input={"comment": comment},
        user_id=owner_id,
        trace_id_seed=feedback_id,
        metadata={
            "feedback_id": feedback_id,
            "user_id": owner_id,
            "user_name": owner_id,
            "source": "sidebar",
        },
    ) as observation:
        observation.update(output={"submitted": True})
    tracer.score_trace(
        feedback_id,
        name="experience-feedback",
        value=comment,
        data_type="TEXT",
        score_id_seed=f"experience-feedback:{feedback_id}",
        comment=comment,
        metadata={
            "feedback_id": feedback_id,
            "user_id": owner_id,
            "source": "sidebar",
        },
    )
    tracer.schedule_flush()
    return ExperienceFeedbackResponse()
