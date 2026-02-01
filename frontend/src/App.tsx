import { Map } from './components/Map/Map';
import { HamburgerMenu } from './components/Menu/HamburgerMenu';
import { SpotModal } from './components/Modal/SpotModal';
import { AboutModal } from './components/Modal/AboutModal';

function App() {
  return (
    <div className="relative">
      <Map />
      <HamburgerMenu />
      <SpotModal />
      <AboutModal />
    </div>
  );
}

export default App;
