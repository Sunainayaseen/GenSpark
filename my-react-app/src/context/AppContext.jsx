import { createContext, useContext, useState, useCallback, useMemo } from 'react';
import { ORDER_STAGES } from '../constants/orderStages';

const AppContext = createContext();

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
};

export const AppProvider = ({ children }) => {
  const [userRequirements, setUserRequirements] = useState({
    purpose: '',
    budget: '',
    city: '',
    preferences: '',
    assembly: true,
  });

  const [selectedBuild, setSelectedBuild] = useState(null);
  const [builds, setBuilds] = useState([]);
  const [orders, setOrders] = useState(() => {
    const demo = [
      {
        id: '1001',
        buildTitle: 'Gaming — Performance Build',
        totalPrice: 132000,
        vendorName: 'Multi-vendor (auto after admin approval)',
        status: 'assembling',
        paymentMethod: 'online',
        timeline: [
          { status: 'pending', message: 'Order placed', timestamp: new Date().toISOString() },
          { status: 'admin-review', message: 'Admin review started', timestamp: new Date().toISOString() },
          { status: 'vendor-orders-generated', message: 'Separate vendor orders generated per component', timestamp: new Date().toISOString() },
          { status: 'assembling', message: 'Assembling', timestamp: new Date().toISOString() },
        ],
        createdAt: new Date().toISOString(),
      },
    ];
    return demo;
  });
  const [user, setUser] = useState(null);
  const [vendors] = useState([
    {
      id: 1,
      name: 'TechAssemble Karachi',
      city: 'Karachi',
      rating: 4.8,
      reviews: 245,
      avgAssemblyTime: '2-3 days',
      serviceCost: 5000,
      phone: '+92 300 1234567',
      address: 'Gulshan-e-Iqbal, Block 5',
      specialties: ['Gaming PCs', 'Workstations', 'Custom Builds'],
      experience: '5+ years',
      status: 'active',
    },
    {
      id: 2,
      name: 'PC Builders Hub Lahore',
      city: 'Lahore',
      rating: 4.6,
      reviews: 189,
      avgAssemblyTime: '3-4 days',
      serviceCost: 4500,
      phone: '+92 300 2345678',
      address: 'DHA Phase 5, Main Boulevard',
      specialties: ['Budget Builds', 'Office PCs', 'Upgrades'],
      experience: '4+ years',
      status: 'active',
    },
    {
      id: 3,
      name: 'Elite Assembly Islamabad',
      city: 'Islamabad',
      rating: 4.9,
      reviews: 312,
      avgAssemblyTime: '2-3 days',
      serviceCost: 5500,
      phone: '+92 300 3456789',
      address: 'F-7 Markaz, Blue Area',
      specialties: ['High-End Builds', 'Content Creation', 'Gaming Rigs'],
      experience: '6+ years',
      status: 'active',
    },
    {
      id: 4,
      name: 'TechZone Rawalpindi',
      city: 'Rawalpindi',
      rating: 4.7,
      reviews: 156,
      avgAssemblyTime: '2-3 days',
      serviceCost: 4800,
      phone: '+92 300 4567890',
      address: 'Saddar, Commercial Area',
      specialties: ['Mid-Range Builds', 'Gaming PCs', 'Repairs'],
      experience: '3+ years',
      status: 'active',
    },
    {
      id: 5,
      name: 'Build Masters Faisalabad',
      city: 'Faisalabad',
      rating: 4.5,
      reviews: 98,
      avgAssemblyTime: '3-4 days',
      serviceCost: 4200,
      phone: '+92 300 5678901',
      address: 'D-Ground, Main Market',
      specialties: ['Budget Builds', 'Office PCs', 'Basic Setups'],
      experience: '2+ years',
      status: 'active',
    },
  ]);

  const updateRequirements = useCallback((data) => {
    setUserRequirements(prev => ({ ...prev, ...data }));
  }, []);

  const resetRequirements = useCallback(() => {
    setUserRequirements({
      purpose: '',
      budget: '',
      city: '',
      preferences: '',
      assembly: true,
    });
  }, []);

  const addOrder = useCallback((order) => {
    const newOrder = {
      id: String(Date.now()),
      status: 'admin-review',
      timeline: [
        { status: 'pending', message: 'Order placed', timestamp: new Date().toISOString() },
        { status: 'admin-review', message: 'Waiting for admin approval', timestamp: new Date().toISOString() },
      ],
      createdAt: new Date().toISOString(),
      ...order,
    };
    setOrders((prev) => [newOrder, ...prev]);
    return newOrder.id;
  }, []);

  const updateOrderStatus = useCallback((orderId, newStatus, message) => {
    setOrders((prev) =>
      prev.map((o) =>
        o.id === orderId
          ? {
              ...o,
              status: newStatus,
              timeline: [
                ...o.timeline,
                { status: newStatus, message: message || ORDER_STAGES.find((s) => s.key === newStatus)?.label || newStatus, timestamp: new Date().toISOString() },
              ],
            }
          : o
      )
    );
  }, []);

  const getOrderById = useCallback((id) => orders.find((o) => o.id === id), [orders]);

  const value = useMemo(
    () => ({
      userRequirements,
      updateRequirements,
      resetRequirements,
      selectedBuild,
      setSelectedBuild,
      builds,
      setBuilds,
      orders,
      setOrders,
      addOrder,
      updateOrderStatus,
      getOrderById,
      user,
      setUser,
      vendors,
    }),
    [
      userRequirements,
      updateRequirements,
      resetRequirements,
      selectedBuild,
      builds,
      orders,
      addOrder,
      updateOrderStatus,
      getOrderById,
      user,
      vendors,
    ]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};







