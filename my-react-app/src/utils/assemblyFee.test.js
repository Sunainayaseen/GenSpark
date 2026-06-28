import { describe, it, expect } from 'vitest';
import { ASSEMBLY_FEE, textNeedsAssembly, cartNeedsAssembly } from './assemblyFee';

describe('ASSEMBLY_FEE', () => {
  it('matches the backend rule (Dashboard/app/services/fees.py)', () => {
    expect(ASSEMBLY_FEE).toBe(5000);
  });
});

describe('textNeedsAssembly', () => {
  it('is true for a CPU + a named motherboard', () => {
    expect(textNeedsAssembly('amd ryzen 7 9800x3d | msi b650 motherboard')).toBe(true);
  });

  it('is true for a CPU + a chipset token paired with a motherboard brand', () => {
    expect(textNeedsAssembly('intel core i5 12400f | asus b660m gaming')).toBe(true);
  });

  it('is false for a CPU + a bare chipset-looking token with no motherboard brand', () => {
    // NZXT H510 is a case, not a motherboard — the bare "H510" token alone must not
    // be trusted as proof of a motherboard (this is the exact false-positive the
    // brand+chipset pairing rule exists to avoid).
    expect(textNeedsAssembly('ryzen 5 5600 | nzxt h510 case')).toBe(false);
  });

  it('is false for a CPU with no motherboard at all', () => {
    expect(textNeedsAssembly('ryzen 5 5600 | corsair 750w psu | 16gb ram')).toBe(false);
  });

  it('is false for a motherboard with no CPU', () => {
    expect(textNeedsAssembly('asus b650 motherboard | 16gb ram')).toBe(false);
  });

  it('is false for an empty or non-PC blob', () => {
    expect(textNeedsAssembly('')).toBe(false);
    expect(textNeedsAssembly(undefined)).toBe(false);
  });
});

describe('cartNeedsAssembly', () => {
  it('reads component_name, title, or name (in that order of preference)', () => {
    const items = [
      { component_name: 'Ryzen 7 9800X3D' },
      { title: 'MSI B650 Motherboard' },
    ];
    expect(cartNeedsAssembly(items)).toBe(true);
  });

  it('is false for accessory-only carts', () => {
    const items = [{ name: 'Logitech Mouse' }, { name: 'Mechanical Keyboard' }];
    expect(cartNeedsAssembly(items)).toBe(false);
  });

  it('is false for an empty cart', () => {
    expect(cartNeedsAssembly([])).toBe(false);
    expect(cartNeedsAssembly(undefined)).toBe(false);
  });
});
