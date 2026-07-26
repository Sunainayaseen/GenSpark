import { Component } from 'react';
import './ErrorBoundary.css';

// Class component is the only way to catch render errors in React (no hook equivalent).
// Scoped around the route tree (not the whole app) so Layout's header/footer/cart drawer
// stay usable even if a single page crashes.
export default class ErrorBoundary extends Component {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error('Unhandled error in route tree:', error, info);
  }

  handleReload = () => {
    this.setState({ hasError: false });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <div className="error-boundary-card">
            <h1>Something went wrong</h1>
            <p>This page hit an unexpected error. Reloading usually fixes it.</p>
            <button type="button" className="btn btn-primary" onClick={this.handleReload}>
              Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
