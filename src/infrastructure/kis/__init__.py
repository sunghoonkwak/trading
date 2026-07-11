"""KIS infrastructure adapters and vendor hook registration."""


def configure_kis_vendor_hooks() -> None:
    """Load host collaborators only when the composition root requests them."""
    from infrastructure.kis.vendor_callbacks import configure_kis_vendor_hooks as configure

    configure()


__all__ = ["configure_kis_vendor_hooks"]
