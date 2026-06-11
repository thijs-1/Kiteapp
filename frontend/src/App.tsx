import { Map } from './components/Map/Map';
import { HamburgerMenu } from './components/Menu/HamburgerMenu';
import { SpotModal } from './components/Modal/SpotModal';
import { AboutModal } from './components/Modal/AboutModal';
import { useSpotFromUrl } from './hooks/useSpotFromUrl';

function App() {
  useSpotFromUrl();

  return (
    <div className="relative">
      <h1 className="sr-only">
        WhereToKite - Find the Best Kitesurfing Spots Worldwide
      </h1>
      <Map />
      <HamburgerMenu />
      <SpotModal />
      <AboutModal />
    </div>
  );
}

export default App;
