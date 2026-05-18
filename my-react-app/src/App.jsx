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
const Chatbot = lazy(() => import("./pages/Chatbot"));
const BuildSuggestions = lazy(() => import("./pages/BuildSuggestions"));
const PrebuiltDetail = lazy(() => import("./pages/PrebuiltDetail"));
const BuildConfigurator = lazy(() => import("./pages/BuildConfigurator"));
const VendorAssignment = lazy(() => import("./pages/VendorAssignment"));
const OrderStatus = lazy(() => import("./pages/OrderStatus"));
const VendorDashboard = lazy(() => import("./pages/VendorDashboard"));
const AdminPanel = lazy(() => import("./pages/AdminPanel"));
const Contact = lazy(() => import("./pages/Contact"));
const About = lazy(() => import("./pages/About"));
import ChangePassword from "./pages/ChangePassword";
const CartPage = lazy(() => import("./pages/CartPage"));
const Checkout = lazy(() => import("./pages/Checkout"));
const EcomCartPage = lazy(() => import("./ecommerce/CartPage"));
const CheckoutPage = lazy(() => import("./ecommerce/CheckoutPage"));
const OrderSuccess = lazy(() => import("./ecommerce/OrderSuccess"));
const AdminEcomPanel = lazy(() => import("./ecommerce/AdminEcomPanel"));
const MyOrders = lazy(() => import("./pages/MyOrders"));
const Components = lazy(() => import("./pages/Components"));

import Layout from "./components/Layout";

import "./App.css";

function RouteFallback() {
  return (
    <div className="page-loading" role="status" aria-live="polite" aria-busy="true">
      <span className="loading-spinner" aria-hidden="true" />
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

// Component to handle page transitions
function AnimatedRoutes() {
  const location = useLocation();

  useEffect(() => {
    const cleanup = initScrollAnimations();

    const mainContent = document.querySelector(".main-content");

    if (mainContent) {
      mainContent.classList.add("page-enter");

      setTimeout(() => {
        mainContent.classList.add("page-enter-active");
        mainContent.classList.remove("page-enter");
      }, 10);
    }

    return () => {
      if (cleanup) cleanup();

      if (mainContent) {
        mainContent.classList.add("page-exit");
        mainContent.classList.add("page-exit-active");

        setTimeout(() => {
          mainContent.classList.remove("page-exit", "page-exit-active");
        }, 300);
      }
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
      <Route path="/ecom/cart" element={<EcomCartPage />} />
      <Route path="/ecom/checkout" element={<CheckoutPage />} />
      <Route path="/ecom/success" element={<OrderSuccess />} />
      <Route path="/ecom/admin" element={<AdminEcomPanel />} />
      <Route path="/my-orders" element={<MyOrders />} />
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

    return () => {
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