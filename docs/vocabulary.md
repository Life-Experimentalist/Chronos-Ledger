# Vocabulary

Two different things get called "vocabulary" in this project, and they behave
nothing alike. Mixing them up is the main way this goes wrong, so they are kept
apart throughout.

**Display labels** are what the interface calls the engine's nouns. They are
cosmetic, they belong to the instance, and changing one changes no data.

**Value sets** are the strings the data actually carries: what is stored in a
column and returned by the API. Some of those are closed sets the engine
branches on. They cannot be renamed from configuration, and they are not meant
to be.

Part 1 covers labels, part 2 covers value sets, part 3 is for anyone building a
system on top of Chronos.

---

## Part 1: display labels

### The six nouns

The engine's own names are neutral. It does not know what a school is.

| Key        | What it is in the engine                                      |
| ---------- | ------------------------------------------------------------- |
| `staff`    | A person who runs sessions. Role `STAFF` in the database.     |
| `member`   | A person whose attendance is recorded. Role `MEMBER`.         |
| `activity` | A recurring thing that gets scheduled. Table `activities`.    |
| `unit`     | The organizational grouping both belong to. `unit_code`.      |
| `lead`     | The person assigned to a specific session, `primary_lead_id`. |
| `cycle`    | The bounded period a schedule is planned within.              |

`staff` and `lead` are separate on purpose. `staff` is a kind of person,
`lead` is a job on one session, and the same person is usually both.

### Setting them

Six environment variables, one per key:

```bash
LABEL_STAFF=Clinician
LABEL_MEMBER=Resident
LABEL_ACTIVITY=Rotation
LABEL_UNIT=Service
LABEL_LEAD=Attending
LABEL_CYCLE=Roster Period
```

Each one is resolved independently, in this order:

1. The environment variable, if it is set to something that is not empty.
2. The `ORG_PROFILE` preset's value for that key.
3. The `generic` value for that key.

So you can set one, or all six, or none. Anything you do not set falls through
to the preset, and the preset falls through to generic. There is no partial
state to get wrong.

The labels are served by `GET /api/v1/config`, which is unauthenticated because
the login page needs them before anybody has signed in. The frontend merges the
response over its own built-in `generic` copy, so an older backend that returns
fewer keys still renders.

Changing a label is safe on a running instance: it touches no schema, no data
and no API field name. Settings are read once at boot, so restart the `app`
container for a change to take effect.

### The presets, and what they are actually for

`ORG_PROFILE` picks one of three starting sets:

| Key        | `generic` | `campus`      | `hospital`    |
| ---------- | --------- | ------------- | ------------- |
| `staff`    | Staff     | Faculty       | Doctor        |
| `member`   | Member    | Student       | Resident      |
| `activity` | Activity  | Course        | Rotation      |
| `unit`     | Unit      | Department    | Department    |
| `lead`     | Lead      | Instructor    | Attending     |
| `cycle`    | Cycle     | Academic Year | Roster Period |

A preset is a starting value. It is not the truth, and it was never going to
be, because a domain does not agree with itself. Two universities in the same
city will disagree on whether the thing is a Course or a Module or a Paper, on
whether the period is a Semester or a Term or a Trimester, and on whether the
grouping is a Department or a School or a Faculty. That last one is worse than
a disagreement: at some institutions "Faculty" is the unit and at others it is
the person, so one preset's `unit` is another preset's `staff`.

The `hospital` set above shows the same problem inside a single row. It calls
`staff` "Doctor" and `member` "Resident", and a resident is a doctor, so the
two labels overlap in a way that reads oddly to anyone who works there. That is
not a bug to be fixed by choosing better words. It is what happens when one set
of words has to serve every hospital.

So the presets are demoted rather than removed. They exist because a fresh
instance needs labels on the first screen, before anyone has configured
anything, and shipping no labels at all is not an option: `generic` is itself a
preset, and the one that has to be right. `LABEL_*` is where the truth lives.
If a preset is wrong for you, that is expected. Override it and move on.

Two things follow from this that are worth being explicit about:

- Do not file an issue asking for a preset to be changed to the words your
  organization uses, and do not add a fourth preset for a domain. The next
  deployment in that domain will disagree with it. Override the six.
- Do not fork the repository to rename things. Everything a rename could
  achieve is already a configuration value, and a fork inherits none of the
  fixes.

### Worked example: a university

```bash
ORG_PROFILE=campus
LABEL_ACTIVITY=Module
LABEL_CYCLE=Trimester
LABEL_UNIT=School
```

The preset supplies Faculty, Student and Instructor, which this institution is
happy with. Three overrides carry the rest. Nothing in the database changes:
the table is still `activities`, the column is still `unit_code`, and the CSV
import still expects the same headers.

### Worked example: a hospital

```bash
ORG_PROFILE=hospital
LABEL_STAFF=Clinician
LABEL_UNIT=Service
```

Two overrides fix the Doctor/Resident overlap described above and swap
Department for Service. `member`, `activity`, `lead` and `cycle` come from the
preset unchanged.

---

## Part 2: value sets

Labels change what a screen says. They do not change what the data is. These
are the strings that actually travel over the API and sit in columns.

### Engine-owned, and closed

These are fixed sets. The engine's own logic branches on them: the generator
decides whether to lay down a session from `DynamicState`, the attendance
percentage counts `VerificationMetric`, and every authorization check in the
codebase reads `InstitutionalRole`. A configurable rename would mean the engine
could no longer reason about its own data.

| Set                     | Values                                                                             |
| ----------------------- | ----------------------------------------------------------------------------------- |
| `InstitutionalRole`     | `SUPER_ADMIN`, `UNIT_ADMIN`, `STAFF`, `MEMBER`                                      |
| `VerificationMetric`    | `PRESENT`, `ABSENT`, `LATE`                                                          |
| `DynamicState`          | `SCHEDULED`, `ON_LEAVE`, `PROXY_SUBSTITUTE`, `LUNCH`, `INTERNAL_MEETING`, `ADHOC_EVENT` |
| `ExecutionMode`         | `PHYSICAL`, `ONLINE_STREAM`                                                          |
| `AccessReadiness`       | `VERY_FREE`, `OPEN_AD_HOC`, `BUSY`, `CRITICAL_DO_NOT_DISTURB`                        |
| `LogVerificationState`  | `PENDING_VERIFICATION`, `VERIFIED_APPROVED`, `VERIFIED_DENIED`                       |
| `ReservationStatus`     | `HELD`, `CANCELLED`                                                                  |
| `ResourceType`          | `ROOM`, `PERSON`                                                                     |

Wanting a different word for one of these on screen is a display problem, and
the six label keys do not cover it: they name nouns, not states. A hospital
that wants `ON_LEAVE` to read "Off rota" has to map it in the client that
renders it. That is a known gap, listed again at the end.

### Instance-owned, and open

`classification_tag` on a ledger annotation is free text, up to 30 characters.
The engine stores it, returns it, and never reads it. There is no fixed set,
deliberately: nothing in this repository defines one and nothing in the
interface writes one, so a guessed set would only refuse whatever an operator
actually types.

That freedom is real but it is not free. Two people tagging the same kind of
event `LATE_START` and `late-start` produce two categories that no report will
ever join. Pick a convention per instance, write it down where the people
typing it will see it, and keep to it.

A knob is proposed for this and not built:

```bash
# Proposed, not implemented.
ANNOTATION_TAGS=LATE_START,EQUIPMENT_FAULT,HANDOVER,INCIDENT
```

Blank would mean free text, exactly as today, so nothing existing breaks. A
non-empty list would restrict the field to those values and let the client
render a dropdown instead of a text box. It is written here as a design rather
than a promise, because whether an instance wants the field constrained is a
question about that instance and not about the engine.

### What labels never touch

Worth stating plainly, because it is the assumption most likely to cause an
integration bug. Setting `LABEL_MEMBER=Student` does not rename anything an
integrator sees. The API field stays `member_id`. The database column stays
`member_id`. The CSV header stays `member_id`. The role stays `MEMBER`. Only
the words on the screen change.

---

## Part 3: building on Chronos

If you are writing a system that uses Chronos as its scheduling authority
rather than deploying Chronos on its own:

1. **Set the six labels for your instance.** Do not rely on a preset matching.
2. **Read `GET /api/v1/config` at startup** rather than hardcoding label
   strings in your own client. It is public, it does not change while a tab is
   open, and it is one request.
3. **Write down your `classification_tag` conventions** before anybody starts
   typing them, and enforce them in your own client if you need them enforced.
4. **Use the engine's names in code and the labels only in views.** Your
   business logic should say `MEMBER`, not "Student". The day someone deploys
   your product at a hospital, only the views should need looking at.
5. **Do not fork the engine to rename things.** See above.

---

## Known limits

Listed so nobody spends an afternoon looking for a setting that is not there.

- **Six keys, singular nouns only.** No plurals, no possessives, no verbs. A
  client that needs "Students" pluralizes the label itself.
- **No labels for states.** The closed sets in part 2 render as they are, or as
  whatever your own client maps them to.
- **Labels are per instance, not per unit.** One deployment cannot call the
  same role Faculty in one department and Clinician in another.
- **No per-locale labels.** One set of words per instance. Translation is a
  larger job than a configuration key.

---

## Related

- [`docs/api.md`](api.md) for the `GET /config` response shape.
- [`README.md`](../README.md#environment-reference) for the environment table.
