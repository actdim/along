import ReactDOM from 'react-dom/client';
import { ComponentContextProvider } from '@actdim/dynstruct/componentModel/react/componentContext';
import { dashboardBus } from './bus';
import { DashboardApiService } from './services/apiService';
import { App } from './App';
import './index.css';

// Initialize the API Service Provider on the message bus
DashboardApiService.start();

const rootElement = document.getElementById('root');
if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <ComponentContextProvider value={{ msgBus: dashboardBus }}>
      <App />
    </ComponentContextProvider>
  );
}
