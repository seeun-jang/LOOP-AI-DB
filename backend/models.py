from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Email = Annotated[str, StringConstraints(strip_whitespace=True, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')]
UserId = Annotated[str, StringConstraints(pattern=r'^[A-Za-z0-9_]{3,50}$')]
Password = Annotated[str, StringConstraints(min_length=10, max_length=128)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Register(Input):
    user_id: UserId
    password: Password
    name: Name
    email: Email


class Login(Input):
    user_id: UserId
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class ProfileUpdate(Input):
    name: Name
    email: Email


class PasswordChange(Input):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: Password


class DeleteAccount(Input):
    password: str = Field(min_length=1, max_length=128)


class SessionCreate(Input):
    topic_id: int = Field(gt=0)
    title: ShortText


class SessionUpdate(Input):
    title: ShortText
    status: Literal['in_progress', 'completed', 'stopped']


class MessageCreate(Input):
    content: Text


class AnswerCreate(Input):
    submitted_answer: Text


class ExperimentCreate(Input):
    question: Text
    prompt_a: Text
    prompt_b: Text


class GeneratedQuestion(Input):
    content: Text
    answer: Text
    explanation: Text


class Grading(Input):
    is_correct: bool = Field(strict=True)
    feedback: Text
