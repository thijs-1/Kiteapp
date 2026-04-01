import { Map } from './components/Map/Map';
import { HamburgerMenu } from './components/Menu/HamburgerMenu';
import { SpotModal } from './components/Modal/SpotModal';
import { AboutModal } from './components/Modal/AboutModal';
import { useSpotFromUrl } from './hooks/useSpotFromUrl';

function App() {
  useSpotFromUrl();

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
