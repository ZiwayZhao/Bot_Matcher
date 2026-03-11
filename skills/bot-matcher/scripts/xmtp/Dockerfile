FROM node:22-slim

WORKDIR /bridge

COPY package.json ./
RUN npm install --production && npm cache clean --force

COPY xmtp_bridge.js ./

# Bridge listens on this port inside the container
EXPOSE 3500

CMD ["node", "xmtp_bridge.js"]
