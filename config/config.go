package config

import (
	"fmt"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

type Config struct {
	SystemNotifications bool `yaml:"system_notifications"`
	// MutePatterns are regular expressions; a notification whose source or body
	// matches any of them is silently dropped. Edited live in config.yaml.
	MutePatterns []string `yaml:"mute_patterns"`
}

func Default() *Config {
	return &Config{
		SystemNotifications: true,
		MutePatterns:        []string{},
	}
}

func Dir() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".config", "mac-notify")
}

func Path() string {
	return filepath.Join(Dir(), "config.yaml")
}

func Load() (*Config, error) {
	cfg := Default()

	data, err := os.ReadFile(Path())
	if err != nil {
		if os.IsNotExist(err) {
			if err := Save(cfg); err != nil {
				return nil, fmt.Errorf("creating default config: %w", err)
			}
			return cfg, nil
		}
		return nil, err
	}

	if err := yaml.Unmarshal(data, cfg); err != nil {
		return nil, fmt.Errorf("parsing config: %w", err)
	}
	return cfg, nil
}

func Save(cfg *Config) error {
	if err := os.MkdirAll(Dir(), 0755); err != nil {
		return err
	}
	data, err := yaml.Marshal(cfg)
	if err != nil {
		return err
	}
	tmp := Path() + ".tmp"
	if err := os.WriteFile(tmp, data, 0644); err != nil {
		return err
	}
	return os.Rename(tmp, Path())
}
