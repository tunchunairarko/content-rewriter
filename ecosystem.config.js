module.exports = {
  apps: [
    {
      name: "content-rewriter",
      cwd: __dirname,
      script: "./start.sh",
      interpreter: "bash",
      exec_mode: "fork",
      instances: 1,
      env: {
        HOST: "0.0.0.0",
        PORT: "8765",
        LOG_DIR: `${__dirname}/logs`,
      },
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 10,
      min_uptime: "20s",
      kill_timeout: 10000,
      max_memory_restart: "400M",
      time: true,
      merge_logs: true,
      out_file: `${__dirname}/logs/pm2-out.log`,
      error_file: `${__dirname}/logs/pm2-error.log`,
    },
  ],
};
