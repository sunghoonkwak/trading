# Portfolio Service Composition (`src/infrastructure/portfolio/composition.py`)

`PortfolioServiceDependencies` groups the concrete collaborators selected by
the composition root for the application `PortfolioService`.

`build_portfolio_service()` injects readiness, source, persistence, weight,
sentiment, and alert collaborators into that use case. This module contains no
portfolio retrieval policy of its own.
