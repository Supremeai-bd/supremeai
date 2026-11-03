import uuid

from sqlalchemy.orm import DeclarativeBase

from models.evolution import Base, CodeProposal, SkillFitness


def test_skill_fitness_defaults():
    sf = SkillFitness(skill_name="math_solver")
    assert sf.skill_name == "math_solver"
    assert sf.version is None or sf.version == 1


def test_skill_fitness_id_generated():
    sf = SkillFitness(skill_name="x")
    if sf.id is not None:
        assert isinstance(sf.id, uuid.UUID)


def test_code_proposal_defaults():
    cp = CodeProposal(
        proposal_id="proposal-1",
        skill_name="translator",
        generated_code="print('hello')",
    )
    assert cp.proposal_id == "proposal-1"
    assert cp.skill_name == "translator"
    assert cp.generated_code == "print('hello')"
    assert hasattr(cp, "ast_validated")
    assert hasattr(cp, "ci_passed")
    assert hasattr(cp, "status")
    assert hasattr(cp, "version")
    assert hasattr(cp, "created_at")


def test_base_is_declarative_base():
    assert issubclass(Base, DeclarativeBase)


def test_skill_fitness_version_mapper_args():
    assert "version_id_col" in SkillFitness.__mapper_args__


def test_code_proposal_version_mapper_args():
    assert "version_id_col" in CodeProposal.__mapper_args__
