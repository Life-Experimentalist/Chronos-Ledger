# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.vocabulary import LABEL_KEYS

# Values that are published in this repository. A deployment running on any of
# them has no secret at all, so production refuses to start rather than serving
# forgeable tokens quietly.
PUBLISHED_SIGNING_KEYS = frozenset(
    {
        # The field default below.
        "insecure_dev_key_change_in_production",
        # The placeholder in .env.example. Copying that file without editing it
        # is the same exposure as never setting the variable.
        "replace_with_64_char_hex_secret_generated_by_openssl_rand_hex_32",
    }
)
# The database passwords published in this repository: the one the field
# default and docker-compose.prod.yml both carried, and the placeholder in
# .env.example. Compared against the password rather than the whole URL,
# because the same password reaches production as @localhost in a bare
# checkout and as @chronos-db under compose, and an exact-URL match saw
# neither of the shapes a deployment actually has.
PUBLISHED_DB_PASSWORDS = frozenset(
    {
        "SecureCloud2026",
        "change_me_password",
    }
)
# The password migration 001 used to seed for the administrator account,
# and the placeholder .env.example carries in its place. Either one lets
# whoever reaches the instance first take an ORG_ADMIN account, so this is
# the same exposure as a published signing key and gets the same refusal.
# Migration 014 rotates a database that still holds the first of them.
PUBLISHED_ADMIN_PASSWORDS = frozenset(
    {
        "ChronosAdmin2026!",
        "replace_with_the_first_admin_password",
    }
)
MINIMUM_SIGNING_KEY_LENGTH = 32
# PASSWORD_MIN_LENGTH may be raised but not lowered past this.
ABSOLUTE_PASSWORD_FLOOR = 8


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: str = "development"
    app_cors_origins: str = "http://localhost:3000,http://localhost"
    # Whether /docs, /redoc and /openapi.json are served. Unset means off in
    # production and on everywhere else, which is the useful default: the
    # interactive docs are how somebody learns this API, and publishing the
    # whole surface of a live instance is how somebody finds the parts of it
    # they were not meant to reach. Set it either way to override.
    docs_enabled: bool | None = None

    # Database
    database_url: str = "postgresql://chronos_admin:SecureCloud2026@localhost:5432/chronos_ledger"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_signing_key: str = "insecure_dev_key_change_in_production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    # The first password for the seeded administrator account, applied on
    # boot while that account is still waiting for one of its own. Empty
    # leaves it unreachable, which is the safe default: this repository
    # publishes no password for anybody to find. See app/core/bootstrap.py.
    initial_admin_password: str = ""

    # The floor on a password a person chooses. Generated passwords are well
    # past it already. Refused below 8: a policy that can be turned down to
    # one character is not a policy, and the first-login gate is built on it.
    password_min_length: int = 12

    # Organization
    org_domain_mask: str = "org.internal"
    # What the interface calls the engine's six nouns, one variable each. Blank
    # means the engine's own neutral word, so an operator sets as few or as
    # many as their words need. There is no preset behind these on purpose: a
    # domain does not agree with itself, and a domain word baked into the
    # engine is one more thing every other deployment has to work around.
    # docs/vocabulary.md has the reasoning and what labels never change.
    label_staff: str = ""
    label_member: str = ""
    label_activity: str = ""
    label_unit: str = ""
    label_lead: str = ""
    label_cycle: str = ""
    # An IANA name, not an offset. "Asia/Kolkata", not "+05:30": an offset
    # cannot know when daylight saving moves, and a schedule that runs across
    # a spring forward would drift by an hour for half the year.
    org_timezone: str = "UTC"

    # VAPID (Web Push)
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_contact_email: str = "admin@org.internal"

    # Telemetry, opt-in. Off by default so a self-hosted instance never
    # reaches a service the operator does not run. Set both to enable.
    telemetry_enabled: bool = False
    telemetry_endpoint: str = ""

    # Rate limits, counted in Redis over a fixed window. Three routes are
    # covered and app/core/rate_limit.py says which and why. A count of 0
    # turns that one limiter off; rate_limit_enabled false turns off all
    # three. The windows are not settings: they are the shape of the
    # limiter, and six variables to describe three limits is a worse deal
    # than three variables and a documented window.
    rate_limit_enabled: bool = True
    # Sign-in, per 15 minutes, two budgets at once. The address budget stops
    # one machine working through a list of accounts; the account budget
    # stops a spread of addresses working on one account.
    rate_limit_login_per_ip: int = 10
    rate_limit_login_per_email: int = 5
    # Visitor check-ins per kiosk account per hour. Deliberately loose: a
    # hospital front desk at visiting hours is genuinely fast, and a limit
    # that interrupts real work gets switched off, which is worse than a
    # loose one.
    rate_limit_guest_checkin: int = 300
    # Calendar feed fetches per feed token per hour. Apple Calendar's
    # fastest refresh is five-minutely, which is twelve an hour on its own,
    # and somebody with a phone and a laptop is two of those.
    rate_limit_calendar_feed: int = 60

    # Largest CSV the timetable upload accepts, in MB. nginx refuses a
    # request over 25 MB before it gets here (client_max_body_size), so
    # raising this past 25 means raising that too.
    csv_upload_max_mb: int = 25

    # How coarse a member's location fix may be, as a multiple of the
    # session's fence radius. A fix that could be 80 m off proves little
    # about a 15 m fence even when its point lands inside. 2 refuses
    # anything coarser than 30 m on the default radius, the same line the
    # web client draws. 0 turns the check off. A mark that reports no
    # accuracy at all is not refused for it.
    geofence_accuracy_factor: float = 2.0

    # How many days a visitor check-in is kept. Each one holds the visitor's
    # name and phone number, and nothing else ever deletes it. A job at 03:30
    # deletes the older ones every day. 0 keeps them forever, which is how an
    # instance behaved before this setting existed.
    guest_retention_days: int = 0

    # How long a visit code opens GET /guest/visit/{code}, in minutes. The code
    # is the visitor's only credential and it is shown to them once, so a code
    # printed or scanned today goes on working for as long as the row lives.
    # Past the window the lookup reads as though the code never existed. 0
    # leaves a code working for as long as the check-in is kept, which is how
    # an instance behaved before this setting existed.
    guest_visit_code_ttl_minutes: int = 0

    # How long an approved visit lasts, in minutes, counted from the decision
    # and not from the check-in: the clock starts when somebody was let in at
    # the door, not when they arrived at it. Past it the visit shows as
    # overstayed at GET /guest/overstays and a notice goes to the desk. Chronos
    # revokes nothing and turns nobody out; the row says the time is up and a
    # person decides what to do about it. 0 leaves an approved visit
    # open-ended, which is how an instance behaved before this setting existed.
    guest_visit_length_minutes: int = 0

    # The largest single extension PATCH /guest/{entry_id}/extend will grant,
    # in minutes. More than this is refused rather than quietly trimmed, so a
    # desk that meant 30 and typed 300 hears about it. A visit can be extended
    # again as often as somebody keeps deciding to, so this bounds one grant
    # and not the total. 0 refuses every extension, for an organization that
    # would rather the visitor checked in again.
    guest_visit_extension_max_minutes: int = 240

    # Whether an admin may decide a visit that was not meant for them, at
    # PATCH /guest/{entry_id}/decide. Off, and with it off the person the
    # visitor came to see is the only one who can let them in, which stalls at
    # the door when that person is in theatre or has gone home for the day. On,
    # an organization admin decides any visit and a unit admin those meant for
    # their own unit, and the row records which of them did.
    #
    # A front desk attendant is not an admin. Give the desk a guest-scoped key
    # on an admin account rather than an admin's password: the scope keeps the
    # key to the visitor log and the role is what this setting reads. The
    # kiosk's own account is a member and stays unable to decide, which is why
    # a lobby tablet does not become an approver when this is turned on.
    guest_admin_can_decide: bool = False

    # Whether a change to a room or a booking is written down for an outside
    # system to poll for, at GET /api/v1/changes/. Off, because it is a table
    # that grows with every write and nothing deletes it, and an instance with
    # no integrator has nobody to read it. Turning it on starts recording from
    # that moment, so a consumer reads the rooms and the bookings once in full
    # and polls from there: what happened while this was off was not recorded.
    change_feed_enabled: bool = False

    # Whether a registered outside issuer may vouch for a person, so that
    # somebody already signed in over there arrives here without a second
    # password. Off, and off means POST /api/v1/auth/federated answers 404
    # rather than 403: whether an instance has an integration is not something
    # probing it should reveal. Turning it on is not enough on its own, since
    # nothing verifies until an issuer is registered. docs/federated-identity.md
    # is the design, threat model first.
    federated_identity_enabled: bool = False

    # The longest life Chronos will accept in a note, in seconds, counted from
    # when it arrives. Checking exp on its own is not enough, because exp is the
    # issuer's opinion and an issuer that sets it a year out has minted a bearer
    # token for a year. This cap is Chronos's opinion, and two minutes is long
    # enough for a browser to hand a note over and short enough that a stolen
    # one is worth little.
    federated_token_max_lifetime_seconds: int = 120

    # How far two clocks may disagree before a perfectly good note is refused,
    # in seconds, and it is not symmetric. exp may be this far in the past, so a
    # note that expired a moment ago on a fast clock still works; iat and nbf
    # may be this far in the future, so a note from a fast issuer works. There
    # is no lower bound on how old a note may be, because that is what exp and
    # the cap above already answer. Widening this widens the replay window by
    # the same amount, so an operator running NTP everywhere can set it lower.
    federated_clock_skew_seconds: int = 60

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.app_cors_origins.split(",") if o.strip()]

    @field_validator("docs_enabled", mode="before")
    @classmethod
    def _blank_means_default(cls, value):
        """DOCS_ENABLED= is "leave it to APP_ENV", not a parse error.

        Both compose files pass ${DOCS_ENABLED:-}, so an operator who never
        sets it hands pydantic an empty string, and bool("") is a
        ValidationError rather than None. That would stop the container
        booting over a variable nobody touched.
        """
        return None if value == "" else value

    @field_validator("password_min_length")
    @classmethod
    def _minimum_is_worth_having(cls, length: int) -> int:
        if length < ABSOLUTE_PASSWORD_FLOOR:
            raise ValueError(
                f"PASSWORD_MIN_LENGTH={length} is below the {ABSOLUTE_PASSWORD_FLOOR} "
                "this refuses to go under. Raise it, or leave it unset for 12."
            )
        return length

    @field_validator("geofence_accuracy_factor")
    @classmethod
    def _factor_is_not_negative(cls, factor: float) -> float:
        if factor < 0:
            raise ValueError(
                f"GEOFENCE_ACCURACY_FACTOR={factor} is negative. Set 0 to turn the "
                "accuracy check off, or leave it unset for 2."
            )
        return factor

    @field_validator("guest_retention_days")
    @classmethod
    def _retention_is_not_negative(cls, days: int) -> int:
        if days < 0:
            raise ValueError(
                f"GUEST_RETENTION_DAYS={days} is negative. Set 0 to keep visitor "
                "check-ins forever, or a number of days such as 90."
            )
        return days

    @field_validator("guest_visit_length_minutes")
    @classmethod
    def _visit_length_is_not_negative(cls, minutes: int) -> int:
        if minutes < 0:
            raise ValueError(
                f"GUEST_VISIT_LENGTH_MINUTES={minutes} is negative. Set 0 to leave an "
                "approved visit open-ended, or a number of minutes such as 120."
            )
        return minutes

    @field_validator("guest_visit_extension_max_minutes")
    @classmethod
    def _extension_max_is_not_negative(cls, minutes: int) -> int:
        if minutes < 0:
            raise ValueError(
                f"GUEST_VISIT_EXTENSION_MAX_MINUTES={minutes} is negative. Set 0 to "
                "refuse every extension, or a number of minutes such as 240."
            )
        return minutes

    @field_validator("guest_visit_code_ttl_minutes")
    @classmethod
    def _ttl_is_not_negative(cls, minutes: int) -> int:
        if minutes < 0:
            raise ValueError(
                f"GUEST_VISIT_CODE_TTL_MINUTES={minutes} is negative. Set 0 to leave "
                "a visit code working for as long as the check-in is kept, or a number "
                "of minutes such as 240."
            )
        return minutes

    @field_validator("federated_token_max_lifetime_seconds")
    @classmethod
    def _lifetime_cap_is_positive(cls, seconds: int) -> int:
        """Zero is not "off" here, it is "refuse every note".

        The other numbers on this page read 0 as a way to turn one check off.
        This one cannot: a cap of zero refuses a note whose exp is even a
        second ahead, which is every note there is, and the failure would look
        like a broken issuer. Turning federation off is
        FEDERATED_IDENTITY_ENABLED.
        """
        if seconds < 1:
            raise ValueError(
                f"FEDERATED_TOKEN_MAX_LIFETIME_SECONDS={seconds} would refuse every "
                "note. Set FEDERATED_IDENTITY_ENABLED=false to turn federated sign-in "
                "off, or leave this unset for 120."
            )
        return seconds

    @field_validator("federated_clock_skew_seconds")
    @classmethod
    def _skew_is_not_negative(cls, seconds: int) -> int:
        if seconds < 0:
            raise ValueError(
                f"FEDERATED_CLOCK_SKEW_SECONDS={seconds} is negative. Set 0 to allow "
                "no disagreement at all, or leave it unset for 60."
            )
        return seconds

    @field_validator("org_timezone")
    @classmethod
    def _zone_must_exist(cls, name: str) -> str:
        """Refuse a name no zone database knows, at startup.

        Unlike the secret checks below this one is a pydantic validator,
        because a timezone name is not a secret and echoing the bad value is
        exactly what the operator needs to see. Falling back to UTC instead
        would put the whole schedule an offset out and say nothing.

        A slim container may have no zone database at all, in which case
        every name but UTC fails here. tzdata is a dependency for that
        reason, so the failure is a typo rather than a missing package.
        """
        try:
            ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError) as bad:
            raise ValueError(
                f"ORG_TIMEZONE={name!r} is not an IANA timezone name. "
                "It wants something like 'Asia/Kolkata' or 'Europe/London', "
                "not an offset like '+05:30'."
            ) from bad
        return name


def label_overrides(settings: Settings) -> dict[str, str]:
    """The LABEL_* values an operator set, shaped for vocabulary.labels_for.

    Here rather than in vocabulary.py so that module keeps knowing nothing
    about settings, the same reason docs_are_published sits here rather than
    in main. Empty values are passed through and dropped there.
    """
    return {key: getattr(settings, f"label_{key}") for key in LABEL_KEYS}


def docs_are_published(settings: Settings) -> bool:
    """Whether this instance serves /docs, /redoc and /openapi.json.

    DOCS_ENABLED decides it when set either way; unset falls back to "anything
    but production". A separate function rather than a method so it can be
    tested without standing up an app, whose app_env is fixed at import time.
    """
    if settings.docs_enabled is not None:
        return settings.docs_enabled
    return settings.app_env != "production"


def describe_production_secret_problems(settings: Settings) -> list[str]:
    """What is wrong with these secrets, in plain sentences, or an empty list.

    Never includes a secret value. The length of a too-short key is named
    because it is what the operator needs to act on; the key itself is not.
    """
    if settings.app_env != "production":
        return []

    problems = []
    if settings.jwt_secret_signing_key in PUBLISHED_SIGNING_KEYS:
        problems.append(
            "JWT_SECRET_SIGNING_KEY is still a placeholder published in this "
            "repository, so anyone can forge a token for any user"
        )
    elif len(settings.jwt_secret_signing_key) < MINIMUM_SIGNING_KEY_LENGTH:
        problems.append(
            f"JWT_SECRET_SIGNING_KEY is {len(settings.jwt_secret_signing_key)} characters, "
            f"below the {MINIMUM_SIGNING_KEY_LENGTH} minimum"
        )
    if any(f":{published}@" in settings.database_url for published in PUBLISHED_DB_PASSWORDS):
        problems.append("DATABASE_URL still carries a password published in this repository")
    if settings.initial_admin_password in PUBLISHED_ADMIN_PASSWORDS:
        problems.append(
            "INITIAL_ADMIN_PASSWORD is a value published in this repository, "
            "so whoever reaches this instance first can take the administrator "
            "account"
        )
    return problems


def assert_production_secrets_are_set(settings: Settings) -> None:
    """Fail the process rather than boot on a public secret.

    Only fires when app_env is production, which is what every deployment path
    sets: both compose files and .env.example. Development keeps the defaults
    so the test suite and a bare checkout still run.

    Deliberately not a pydantic model_validator. Pydantic decorates a
    ValidationError with `input_value=...`, which would echo the very secret
    being complained about into the logs.
    """
    problems = describe_production_secret_problems(settings)
    if not problems:
        return
    raise RuntimeError(
        "Refusing to start with APP_ENV=production:\n  - "
        + "\n  - ".join(problems)
        + "\n\nRun ./setup.sh, which generates them, or set them yourself:\n"
        "  JWT_SECRET_SIGNING_KEY=$(openssl rand -hex 32)"
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    assert_production_secrets_are_set(settings)
    return settings
