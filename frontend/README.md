# GenSpark Builds - AI-Powered PC Customization Platform

A modern, fully responsive React application for building custom PCs with AI-powered compatibility checking, local vendor assignment, and real-time order tracking.

## 🚀 Features

### Core Functionality
- **AI-Powered Build Generation**: Smart compatibility checking ensures all parts work together
- **Interactive Chatbot**: Collects user requirements (purpose, budget, city, preferences)
- **Build Suggestions**: Multiple build options (Performance, Balanced, Budget)
- **Build Configurator**: Swap parts, view compatibility warnings, and customize builds
- **Vendor Assignment**: City-based vendor selection with ratings and reviews
- **Order Tracking**: Real-time status updates with WhatsApp notifications preview
- **Vendor Dashboard**: Manage orders, accept/decline, upload build photos
- **Admin Panel**: Validate builds, review compatibility, approve orders

### Design Features
- **Modern UI**: Beautiful gradient colors, smooth animations, and humanized design
- **Fully Responsive**: Works seamlessly on desktop, tablet, and mobile devices
- **Accessible**: Clean, intuitive navigation and user experience
- **Color Scheme**: 
  - Primary: Indigo (#6366f1) - Trust & Technology
  - Secondary: Pink (#ec4899) - Energy & Innovation
  - Accent: Amber (#f59e0b) - Warmth & Action

## 📁 Project Structure

```
src/
├── components/
│   ├── Layout.jsx          # Main layout with header and footer
│   └── Layout.css
├── context/
│   └── AppContext.jsx      # Global state management
├── pages/
│   ├── Landing.jsx          # Home page with hero and quick builds
│   ├── Chatbot.jsx         # Requirement collection chatbot
│   ├── BuildSuggestions.jsx # Build recommendations grid
│   ├── BuildConfigurator.jsx # Parts customization tool
│   ├── VendorAssignment.jsx  # Vendor selection and payment
│   ├── OrderStatus.jsx     # Order tracking with timeline
│   ├── VendorDashboard.jsx # Vendor order management
│   └── AdminPanel.jsx      # Admin validation panel
├── App.jsx                 # Main app with routing
├── App.css
├── main.jsx                # Entry point
└── index.css              # Global styles and design system
```

## 🎨 Pages Overview

### 1. Landing Page (`/`)
- Hero section with call-to-action
- Quick build cards (Budget, Gaming Pro, Content Creator)
- Features showcase

### 2. Chatbot (`/chatbot`)
- Step-by-step requirement collection
- Progress tracking sidebar
- Quick reply chips for common answers
- Context summary of collected data

### 3. Build Suggestions (`/builds`)
- Grid of 3 build recommendations
- Comparison mode (side-by-side)
- Part details with clickable specs
- Customize and Proceed actions

### 4. Build Configurator (`/configurator`)
- Visual parts list with icons
- Compatibility status panel
- Price breakdown
- Part swapping with filters
- Compatibility warnings

### 5. Vendor Assignment (`/vendor-assignment`)
- City-filtered vendor list
- Vendor ratings and reviews
- Assembly vs parts-only options
- Payment method selection
- Order summary

### 6. Order Status (`/order/:id`)
- Status timeline with progress bar
- WhatsApp notification previews
- Order details and vendor info
- Contact vendor button

### 7. Vendor Dashboard (`/vendor/dashboard`)
- Incoming orders list
- Accept/Decline actions
- Upload build photos
- Order details and required tools
- Navigation: Orders, Availability, Profile, Earnings

### 8. Admin Panel (`/admin`)
- Build validation queue
- Compatibility checks (pass/warning/fail)
- Build photos review
- Audit logs
- Approve/Flag/Rework actions
- Navigation: Validation, Parts DB, Vendors

## 🛠️ Technologies Used

- **React 19** - UI library
- **React Router DOM** - Client-side routing
- **Vite** - Build tool and dev server
- **CSS3** - Custom styling with CSS variables
- **Context API** - State management

## 📦 Installation & Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Start development server:**
   ```bash
   npm run dev
   ```

3. **Build for production:**
   ```bash
   npm run build
   ```

4. **Preview production build:**
   ```bash
   npm run preview
   ```

## 🎯 User Flows

### Buyer Flow
1. Land on homepage → Click "Start Build"
2. Chatbot collects requirements
3. View build suggestions → Select or customize
4. Choose vendor → Select payment method
5. Track order status → Receive WhatsApp updates
6. Delivery → Provide feedback

### Vendor Flow
1. Access vendor dashboard
2. View incoming orders
3. Accept/Decline orders
4. Upload build photos
5. Mark as assembled

### Admin Flow
1. Access admin panel
2. Review validation queue
3. Check compatibility and photos
4. Approve/Flag/Request rework
5. Monitor audit logs

## 🎨 Design System

### Colors
- **Primary**: `#6366f1` (Indigo)
- **Secondary**: `#ec4899` (Pink)
- **Success**: `#10b981` (Green)
- **Warning**: `#f59e0b` (Amber)
- **Error**: `#ef4444` (Red)

### Typography
- Font Family: Inter, system fonts
- Headings: 700 weight
- Body: 400 weight, 1.6 line-height

### Spacing
- Uses CSS custom properties for consistent spacing
- Responsive breakpoints at 768px and 1200px

## 📱 Responsive Design

- **Desktop**: Full layout with sidebars and multi-column grids
- **Tablet**: Adjusted grid layouts, collapsible sidebars
- **Mobile**: Single column, hamburger menu, stacked cards

## 🔮 Future Enhancements

- Backend API integration (FastAPI)
- Real WhatsApp API integration
- Payment gateway integration
- User authentication
- Database integration
- Real-time notifications
- Advanced filtering and search
- Build sharing and saving
- Reviews and ratings system

## 📝 Notes

- Currently uses mock data for demonstration
- All API calls are simulated
- WhatsApp notifications are preview-only
- Payment processing is UI-only

## 👨‍💻 Development

The app is built with modern React patterns:
- Functional components with hooks
- Context API for state management
- React Router for navigation
- CSS modules for component styling
- Responsive design principles

---

Built with ❤️ using React + Vite
