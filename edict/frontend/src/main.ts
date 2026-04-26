import { createApp } from 'vue';
import { createPinia } from 'pinia';
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  ConfigProvider,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  List,
  Menu,
  Modal,
  Popconfirm,
  Progress,
  Segmented,
  Select,
  Skeleton,
  Space,
  Statistic,
  Switch,
  Table,
  Tag,
  Timeline,
} from 'ant-design-vue';
import 'ant-design-vue/dist/reset.css';
import App from './App.vue';
import './index.css';

const app = createApp(App);

app.use(createPinia());
[
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  ConfigProvider,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  List,
  Menu,
  Modal,
  Popconfirm,
  Progress,
  Segmented,
  Select,
  Skeleton,
  Space,
  Statistic,
  Switch,
  Table,
  Tag,
  Timeline,
].forEach((component) => app.use(component));

app.mount('#app');
