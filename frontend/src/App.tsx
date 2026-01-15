import { Map } from './components/Map/Map';
import { HamburgerMenu } from './components/Menu/HamburgerMenu';
import { SpotModal } from './components/Modal/SpotModal';

function App() {
  return (
    <div className="relative">
      <Map />
      <HamburgerMenu />
      <SpotModal />
    </div>
  );
}

export default App;
