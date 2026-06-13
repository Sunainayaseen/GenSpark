import { BrowserRouter as Router, Routes, Route, useLocation, Navigate } from "react-router-dom";
import { useEffect, lazy, Suspense } from "react";
import axios from "axios";

import { AppProvider } from "./context/AppContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { CartProvider } from "./context/CartContext";

import { initScrollAnimations } from "./utils/scrollAnimations";
import { initParallax } from "./utils/parallax";
import { getApiUrl } from "./utils/flaskBase";

import Landing from "./pages/Landing";
import About from "./pages/About";
import Components from "./pages/Components";
import BuildSuggestions from "./pages/BuildSuggestions";
import Chatbot from "./pages/Chatbot";
const PrebuiltDetail = lazy(() => import("./pages/PrebuiltDetail"));
const BuildConfigurator = lazy(() => import("./pages/BuildConfigurator"));
const VendorAssignment = lazy(() => import("./pages/VendorAssignment"));
const OrderStatus = lazy(() => import("./pages/OrderStatus"));
const VendorDashboard = lazy(() => import("./pages/VendorDashboard"));
const AdminPanel = lazy(() => import("./pages/AdminPanel"));
const Contact = lazy(() => import("./pages/Contact"));
import ChangePassword from "./pages/ChangePassword";
const CartPage = lazy(() => import("./pages/CartPage"));
const Checkout = lazy(() => import("./pages/Checkout"));
const OrderPlacedSuccess = lazy(() => import("./pages/OrderPlacedSuccess"));
const EcomCartPage = lazy(() => import("./ecommerce/CartPage"));
const CheckoutPage = lazy(() => import("./ecommerce/CheckoutPage"));
const OrderSuccess = lazy(() => import("./ecommerce/OrderSuccess"));
const AdminEcomPanel = lazy(() => import("./ecommerce/AdminEcomPanel"));
const MyOrders = lazy(() => import("./pages/MyOrders"));
const TrackOrder = lazy(() => import("./pages/TrackOrder"));

import Layout from "./components/Layout";
import StripeVerifyTest from "./components/StripeVerifyTest";
import { prefetchMainNavRoutes } from "./utils/routePrefetch";

import "./App.css";

function RouteFallback() {
  return (
    <div className="route-loading" role="status" aria-live="polite" aria-busy="true">
      <div className="route-loading-bar" aria-hidden="true" />
      <span className="sr-only">Loading page</span>
    </div>
  );
}


// Redirect to change-password when user must change password (first login after admin add).
function MustChangePasswordGate({ children }) {
  const { user } = useAuth();
  const location = useLocation();
  if (user?.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }
  return children;
}

function AnimatedRoutes() {
  const location = useLocation();

  useEffect(() => {
    window.scrollTo(0, 0);
    const cleanup = initScrollAnimations();
    return () => {
      if (cleanup) cleanup();
    };
  }, [location.pathname]);

  return (
    <Routes location={location}>
      <Route path="/" element={<Landing />} />
      <Route path="/chatbot" element={<Chatbot />} />
      <Route path="/builds/prebuilt/:id" element={<PrebuiltDetail />} />
      <Route path="/builds" element={<BuildSuggestions />} />
      <Route path="/components" element={<Components />} />
      <Route path="/configurator" element={<BuildConfigurator />} />
      <Route path="/vendor-assignment" element={<VendorAssignment />} />
      <Route path="/cart" element={<CartPage />} />
      <Route path="/checkout" element={<Checkout />} />
      <Route path="/stripe-verify" element={<StripeVerifyTest />} />
      <Route path="/order-success" element={<OrderPlacedSuccess />} />
      <Route path="/ecom/cart" element={<EcomCartPage />} />
      <Route path="/ecom/checkout" element={<CheckoutPage />} />
      <Route path="/ecom/success" element={<OrderSuccess />} />
      <Route path="/ecom/admin" element={<AdminEcomPanel />} />
      <Route path="/my-orders" element={<MyOrders />} />
      <Route path="/track/:orderId" element={<TrackOrder />} />
      <Route path="/order/:id" element={<OrderStatus />} />
      <Route path="/change-password" element={<ChangePassword />} />
      <Route path="/vendor/dashboard" element={<VendorDashboard />} />
      <Route path="/admin" element={<AdminPanel />} />
      <Route path="/contact" element={<Contact />} />
      <Route path="/about" element={<About />} />
    </Routes>
  );
}


function App() {
  useEffect(() => {
    const scrollCleanup = initScrollAnimations();
    const parallaxCleanup = initParallax();

    const fetchApi = async () => {
      try {
        const response = await axios.get(getApiUrl('/message'));
        if (response.data?.message) console.log(response.data.message);
      } catch (error) {
        console.error(error);
      }
    };

    fetchApi();

    const idleId =
      typeof requestIdleCallback === 'function'
        ? requestIdleCallback(() => prefetchMainNavRoutes(), { timeout: 2500 })
        : window.setTimeout(prefetchMainNavRoutes, 600);
    return () => {
      if (typeof requestIdleCallback === 'function' && typeof cancelIdleCallback === 'function') {
        cancelIdleCallback(idleId);
      } else {
        clearTimeout(idleId);
      }
      if (scrollCleanup) scrollCleanup();
      if (parallaxCleanup) parallaxCleanup();
    };
  }, []);

  return (
    <AuthProvider>
      <AppProvider>
        <CartProvider>
          <Router>
            <Layout>
              <MustChangePasswordGate>
                <Suspense fallback={<RouteFallback />}>
                  <AnimatedRoutes />
                </Suspense>
              </MustChangePasswordGate>
            </Layout>
          </Router>
        </CartProvider>
      </AppProvider>
    </AuthProvider>
  );
}

export default App;