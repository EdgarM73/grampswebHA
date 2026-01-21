"""API client for Gramps Web."""
import logging
from datetime import datetime, date
import requests

_LOGGER = logging.getLogger(__name__)


class GrampsWebAPI:
    """Class to interact with Gramps Web API."""

    def __init__(self, url: str, username: str = None, password: str = None):
        """Initialize the API client."""
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self.token = None
        self._session = requests.Session()

    def _authenticate(self):
        """Authenticate with the Gramps Web API."""
        if not self.username or not self.password:
            return True
        
        try:
            response = self._session.post(
                f"{self.url}/api/token/",
                json={
                    "username": self.username,
                    "password": self.password,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            self.token = data.get("access_token")
            
            if self.token:
                self._session.headers.update({
                    "Authorization": f"Bearer {self.token}"
                })
            return True
        except Exception as err:
            _LOGGER.warning("Failed to authenticate with Gramps Web: %s", err)
            return False

    def _get(self, endpoint: str, params: dict = None):
        """Make a GET request to the API."""
        if not self.token and self.username:
            self._authenticate()
        
        try:
            response = self._session.get(
                f"{self.url}/api/{endpoint}",
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except Exception as err:
            _LOGGER.error("API request failed: %s", err)
            raise

    def get_people(self):
        """Get all people from Gramps Web."""
        return self._get("people/")

    def get_birthdays(self, limit: int = 50):
        """Get upcoming birthdays from Gramps Web."""
        try:
            # Get all people
            people_data = self.get_people()
            birthdays = []
            
            today = date.today()
            current_year = today.year
            
            for person in people_data:
                # Get birth event
                birth_date = self._extract_birth_date(person)
                if not birth_date:
                    continue
                
                # Calculate next birthday
                name = self._get_person_name(person)
                next_birthday_info = self._calculate_next_birthday(birth_date, name)
                
                if next_birthday_info:
                    birthdays.append(next_birthday_info)
            
            # Sort by days until birthday
            birthdays.sort(key=lambda x: x["days_until"])
            
            return birthdays[:limit]
            
        except Exception as err:
            _LOGGER.error("Failed to fetch birthdays: %s", err)
            raise

    def _extract_birth_date(self, person: dict):
        """Extract birth date from person data."""
        try:
            # Try to get birth event reference
            event_ref = person.get("event_ref_list", [])
            for event in event_ref:
                if event.get("role") == "Primary":
                    # In real implementation, you'd need to fetch the event details
                    # For now, check if birth data is in profile
                    pass
            
            # Alternative: check profile data
            profile = person.get("profile", {})
            birth = profile.get("birth")
            
            if birth:
                return self._parse_gramps_date(birth)
            
            return None
            
        except Exception as err:
            _LOGGER.debug("Could not extract birth date: %s", err)
            return None

    def _parse_gramps_date(self, date_str: str):
        """Parse Gramps date format to Python date."""
        try:
            # Gramps can have various date formats
            # Common format: "1990-01-15" or "15 Jan 1990"
            if "-" in date_str and len(date_str) == 10:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            # Add more parsing logic as needed
            return None
        except Exception:
            return None

    def _get_person_name(self, person: dict):
        """Get person's display name."""
        try:
            profile = person.get("profile", {})
            name_given = profile.get("name_given", "")
            name_surname = profile.get("name_surname", "")
            return f"{name_given} {name_surname}".strip()
        except Exception:
            return "Unknown"

    def _calculate_next_birthday(self, birth_date: date, name: str):
        """Calculate next birthday occurrence."""
        try:
            today = date.today()
            current_year = today.year
            
            # Calculate this year's birthday
            this_year_birthday = birth_date.replace(year=current_year)
            
            # If birthday already passed this year, use next year
            if this_year_birthday < today:
                next_birthday = birth_date.replace(year=current_year + 1)
            else:
                next_birthday = this_year_birthday
            
            days_until = (next_birthday - today).days
            age = next_birthday.year - birth_date.year
            
            return {
                "person_name": name,
                "birth_date": birth_date.isoformat(),
                "next_birthday": next_birthday.isoformat(),
                "age": age,
                "days_until": days_until,
            }
            
        except Exception as err:
            _LOGGER.debug("Could not calculate birthday for %s: %s", name, err)
            return None
