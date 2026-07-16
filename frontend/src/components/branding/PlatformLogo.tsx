type PlatformLogoVariant = 'full' | 'compact' | 'header';

type PlatformLogoProps = {
  variant?: PlatformLogoVariant;
  className?: string;
  altText?: string;
};

const logoByVariant: Record<PlatformLogoVariant, string> = {
  full: '/branding/security-platform-logo-full.png',
  compact: '/branding/security-platform-logo-compact.png',
  header: '/branding/security-platform-logo-header.png',
};

export function PlatformLogo({ variant = 'header', className, altText = 'Security Platform' }: PlatformLogoProps) {
  return <img className={className} src={logoByVariant[variant]} alt={altText} />;
}
