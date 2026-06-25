import { createContext, useContext } from 'react';

const AppContext = createContext({});
export default AppContext;
export function useApp() { return useContext(AppContext); }
