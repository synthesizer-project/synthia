API Reference
*************

.. autosummary::
   :toctree: _autosummary
   :recursive:

   synthia

Internal safety helpers
=======================

``synthia._safety`` is private, so autosummary skips it, but it holds the
containment, truncation and untrusted-envelope primitives that every tool's
safety boundary is built from. It is documented here because those guarantees
are part of Synthia's contract.

.. automodule:: synthia._safety
   :members:
