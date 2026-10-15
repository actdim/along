import ReactDOM from 'react-dom/client';
import { ComponentContextProvider } from '@actdim/dynstruct/componentModel/react/componentContext';
import { dashboardBus } from './bus';
import { App } from './App';
import './index.css';

const rootElement = document.getElementById('root');
if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <ComponentContextProvider value={{ msgBus: dashboardBus }}>
      <App />
    </ComponentContextProvider>
  );
}
