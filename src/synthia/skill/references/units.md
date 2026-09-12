# Units and the `Quantity` Descriptor

Everything here is about `unyt` and Synthesizer's unit system. Where files live
on this machine is `local-grids.md`; what the catalogue publishes is
`data-catalogue.md`.

## The `Quantity` descriptor

Synthesizer attaches units to almost every physical attribute using a `Quantity`
descriptor (`synthesizer.units`). The behaviour is specific and worth learning
properly, because getting it wrong produces wrong numbers rather than errors.

**Public attribute versus underscore attribute:**

- `obj.attr` returns a `unyt` array **with units attached**.
- `obj._attr` returns a **bare numpy array**, already converted to that
  `Quantity`'s own unit. On a stock install that is the default unit for the
  quantity's category, but `Quantity.__set_name__` overrides it if `Units` was
  given a per-attribute unit under that attribute's name, so check the
  configuration before assuming the category default.

`obj._attr` is *not* the raw value the user supplied or the value as stored in a
file. It is the converted value with the units stripped off. Use it for speed
and for plotting; never use it to reason about what the user passed in.

**Construction raises; assignment converts silently.** These are two different
mechanisms and they fail in opposite ways.

*Constructors and functions decorated with `@accepts(...)` raise* on a value
with no units. This is most of the emitter constructors, so the common beginner
mistake is caught:

```text
Stars(initial_masses=..., ages=np.full(3, 10.0), metallicities=...)
MissingUnits: ages is missing units! Expected to be in Myr (or equivalent).
```

Note the unit in that message is the **per-parameter unit the decorator
demands** (`Myr` for `ages`), which is not the same as the *category default*
that the value will be stored in (`yr` for time). Both are correct; they answer
different questions. Do not let the mismatch make you doubt the diagnosis — the
fix is simply to attach units.

*Assignment after construction does not raise.* Setting a public `Quantity`
attribute converts silently, and the object does not remember the input unit:

```text
s.ages = np.full(3, 10.0)      -> [10. 10. 10.] yr    (bare: assumed default)
s.coordinates = arr * kpc      -> stored as Mpc       (converted, not tagged)
```

Dimensionless input bypasses conversion entirely, and a bare value is assumed to
already be in the category default. So a bare `10` assigned to `ages` means ten
**years**, not ten Myr. This is the silent-error path: it produces wrong numbers
rather than an exception, and only assignment reaches it. Always attach units.

## Default unit categories

There are 17 categories (spatial, mass, time, wavelength, luminosity, the
luminosity and flux densities, velocity, temperature, angle, angular resolution,
frequency, and mass rate among them). Rather than trusting a copy of the values,
read the effective configuration: `BASE_DIR/default_units.yml`, whose path
`inspect_environment` reports (`BASE_DIR` itself is in `local-grids.md`). That file is the authority, and it is per-user
(see below).

## The `Units` singleton

`Units` is a **singleton**, enforced by a metaclass. Two consequences:

- Re-instantiating `Units(...)` with a new dictionary does **nothing**. It
  returns the existing instance. Overriding requires `force=True`, and doing so
  is explicitly discouraged in the source.
- Changing units does **not retroactively convert** quantities that already
  exist. Anything constructed before the change keeps its old numbers with new
  labels — which is worse than an error. Set units before building anything, or
  not at all.

The effective unit configuration is the **user's own copy**, written to
`BASE_DIR/default_units.yml` on first import — not the copy inside the installed
package. Editing the package copy has no effect. If a user reports units that do
not match the documentation, check their file.
