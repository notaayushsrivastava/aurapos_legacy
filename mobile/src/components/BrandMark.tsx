import { LinearGradient } from 'expo-linear-gradient';
import { Feather } from '@expo/vector-icons';
import { StyleSheet } from 'react-native';

/**
 * The AuraPOS brand mark — replicates the web sidebar logo exactly:
 * a rounded-xl chip filled with the magenta → violet → cyan gradient,
 * a white lucide/feather "scissors" glyph, and a soft magenta glow.
 */
export function BrandMark({ size = 36, iconSize = 18 }: { size?: number; iconSize?: number }) {
  return (
    <LinearGradient
      colors={['#f72585', '#7c3aed', '#00f5d4']}
      start={{ x: 0, y: 1 }}
      end={{ x: 1, y: 0 }}
      style={[
        styles.chip,
        {
          width: size,
          height: size,
          borderRadius: Math.round(size * 0.31), // rounded-xl proportion
          shadowRadius: size * 0.45,
        },
      ]}
    >
      <Feather name="scissors" size={iconSize} color="#ffffff" />
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  chip: {
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#f72585',
    shadowOpacity: 0.25,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
});
