import { createRoot } from 'react-dom/client';
import App from './App';
import '@taragold/shared/globals.css';
import './storefront-theme.css';

createRoot(document.getElementById('root')!).render(<App />);