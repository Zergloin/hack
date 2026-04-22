from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.region import Region  # noqa: E402, F401
from app.models.municipality import Municipality  # noqa: E402, F401
from app.models.population import PopulationRecord  # noqa: E402, F401
from app.models.demographics import DemographicIndicator  # noqa: E402, F401
from app.models.forecast import Forecast  # noqa: E402, F401
from app.models.report import Report  # noqa: E402, F401
